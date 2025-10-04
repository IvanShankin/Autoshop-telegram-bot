from datetime import datetime, timezone

import orjson
from dateutil.parser import parse
from sqlalchemy import select, update, delete

from src.exceptions.service_exceptions import UserNotFound
from src.services.admins.models import AdminActions
from src.services.referrals.utils import create_unique_referral_code
from src.services.users.models import Users, NotificationSettings, BannedAccounts, UserAuditLogs
from src.services.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.time_storage import TIME_USER
from src.utils.send_messages import send_log


async def get_user(user_id: int, username: str = None)->Users | None:
    """
    Берёт с redis, если там нет, то возьмёт с БД и запишет в redis.
    :param username: обновит username если он не сходится с имеющимся
    """
    async with get_redis() as session_redis:
        user_redis = await session_redis.get(f'user:{user_id}')
        if user_redis:
            data = orjson.loads(user_redis)
            user = Users(
                user_id=data["user_id"],
                username=data.get("username"),
                language=data.get("language"),
                unique_referral_code=data.get("unique_referral_code"),
                balance=data.get("balance", 0),
                total_sum_replenishment=data.get("total_sum_replenishment", 0),
                total_profit_from_referrals=data.get("total_profit_from_referrals", 0),
                created_at=parse(data["created_at"]) if data.get("created_at") else None,
            )
            if username and user.username and user.username != username: # если username расходится
                user.username = username
                user = await update_user(user)
            return user

    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users).where(Users.user_id == user_id))
        user_db = result_db.scalar_one_or_none()
        if user_db:
            if username and user_db.username and user_db.username != username: # если username расходится
                user_db.username = username
                user_db = await update_user(user_db)

            async with get_redis() as session_redis:
                await session_redis.setex(f'user:{user_id}', TIME_USER, orjson.dumps(user_db.to_dict()))
            return user_db
        else:
            return None


async def add_new_user(user_id: int, username: str, language: str = 'ru'):
    """Создаст нового пользователя и прикрепит к нему настройки уведомлений"""
    user = Users(
        user_id = user_id,
        username = username,
        language = language,
        unique_referral_code = create_unique_referral_code(),
        balance = 0,
        total_sum_replenishment = 0,
        total_profit_from_referrals = 0,
        created_at = datetime.now(timezone.utc)
    )
    new_notification = NotificationSettings(
        user_id = user_id
    )
    new_log = UserAuditLogs(
        user_id=user_id,
        action_type = "new_user"
    )
    async with get_db() as session_db:
        session_db.add(user)
        await session_db.commit()
        session_db.add(new_notification)
        session_db.add(new_log)
        await session_db.commit()

    async with get_redis() as session_redis:
        await session_redis.setex(f'user:{user_id}', TIME_USER, orjson.dumps(user.to_dict()))

    await send_log(f"#Новый_пользователь \n\nID: {user_id}\nusername: {username}")


async def update_user(user: Users) -> Users:
    """
    Обновляет данные пользователя в БД и Redis.
    :param user Объект пользователя с обновленными данными
    """
    # Обновляем в БД
    async with get_db() as session_db:
        # Выполняем обновление
        result = await session_db.execute(
            update(Users)
            .where(Users.user_id == user.user_id)
            .values(
                username = user.username,
                language = user.language,
                unique_referral_code = user.unique_referral_code,
                balance = user.balance,
                total_sum_replenishment = user.total_sum_replenishment,
                total_profit_from_referrals = user.total_profit_from_referrals
            )
            .returning(Users.created_at)
        )
        created_at = result.scalar_one()
        await session_db.commit()

    user.created_at = created_at # т.к. может поступить дата от пользователя, которая не верна

    # Обновляем в Redis
    async with get_redis() as session_redis:
        await session_redis.setex(
            f'user:{user.user_id}',
            TIME_USER,
            orjson.dumps(user.to_dict())
        )
    return user


async def get_notification(user_id) -> NotificationSettings | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
        return result_db.scalar_one_or_none()

async def update_notification(
        user_id: int,
        referral_invitation: bool,
        referral_level_up: bool,
        referral_replenishment: bool
) -> NotificationSettings | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(
            update(NotificationSettings)
            .where(NotificationSettings.user_id == user_id)
            .value(
                referral_invitation = referral_invitation,
                referral_level_up = referral_level_up,
                referral_replenishment = referral_replenishment
            )
            .returning(NotificationSettings)
        )
        return result_db.scalar_one_or_none()

async def get_banned_account(user_id: int) -> str | None:
    """
    Проверит только в redis
    :return: Причина бана, если забанен иначе None
    """
    async with get_redis() as session_redis:
        result_redis = await session_redis.get(f"banned_account:{user_id}")

    return None if result_redis is None else result_redis


async def add_banned_account(admin_id: int, user_id: int, reason: str):
    """
    Создаст новый забаненный аккаунт, залогирует и отошлёт в канал данное действие админа
    :param admin_id: id админа который это сделал
    :param user_id: id пользователя
    :param reason: Причина
    :exception UserNotFound: Если пользователь не найден
    """
    if not await get_user(user_id):
        raise UserNotFound(f"Пользователь с id = {user_id} не найден")

    new_ban = BannedAccounts(
        user_id = user_id,
        reason = reason
    )
    new_admin_log = AdminActions(
        user_id=admin_id,
        action_type = "added ban account",
        details = {'message': "Добавил аккаунт в забаненные", "user_id": user_id }
    )
    async with get_db() as session_db:
        session_db.add(new_ban)
        session_db.add(new_admin_log)
        await session_db.commit()

    async with get_redis() as session_redis:
        await session_redis.set(f"banned_account:{user_id}", reason)

    await send_log(
        f"#Аккаунт_забанен \n\n"
        f"Админ c ID = '{admin_id}' \n"
        f"Добавил нового пользователя в забаненные аккаунты \n\n"
        f"ID Пользователя: '{user_id}'\n"
        f"Причина: '{reason}'"
    )

async def delete_banned_account(admin_id: int, user_id: int):
    if not await get_banned_account(user_id):
        raise UserNotFound(f"Пользователь с id = {user_id} не забанен")

    new_admin_log = AdminActions(
        user_id=admin_id,
        action_type="added ban account",
        details={'message': "Добавил аккаунт в забаненные", "user_id": user_id}
    )

    async with get_db() as session_db:
        await session_db.execute(delete(BannedAccounts).where(BannedAccounts.user_id == user_id))
        await session_db.add(new_admin_log)
        await session_db.commit()

    await send_log(
        f"#Аккаунт_разбанен \n\n"
        f"Админ c ID = '{admin_id}' разбанил пользователя \n"
        f"ID разбаненного аккаунта: '{user_id}'"
    )
