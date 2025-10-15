from datetime import datetime, timezone

import orjson
from sqlalchemy import select, update, delete

from src.exceptions.service_exceptions import UserNotFound
from src.services.admins.models import AdminActions
from src.services.referrals.utils import create_unique_referral_code
from src.services.users.actions.action_user import get_user
from src.services.users.models import Users, NotificationSettings, BannedAccounts, UserAuditLogs
from src.services.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.time_storage import TIME_USER
from src.bot_actions.actions import send_log

async def add_new_user(user_id: int, username: str, language: str = 'ru') -> Users:
    """Создаст нового пользователя и прикрепит к нему настройки уведомлений"""
    user = Users(
        user_id = user_id,
        username = username,
        language = language,
        unique_referral_code = await create_unique_referral_code(),
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
        await session_db.refresh(user)

    async with get_redis() as session_redis:
        await session_redis.setex(f'user:{user_id}', TIME_USER, orjson.dumps(user.to_dict()))

    await send_log(f"#Новый_пользователь \n\nID: {user_id}\nusername: {username}")

    return user

async def get_notification(user_id) -> NotificationSettings | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
        return result_db.scalar_one_or_none()

async def update_notification(
        user_id: int,
        referral_invitation: bool,
        referral_replenishment: bool
) -> NotificationSettings | None:
    async with (get_db() as session_db):
        result_db = await session_db.execute(
            update(NotificationSettings)
            .where(NotificationSettings.user_id == user_id)
            .values(
                referral_invitation = referral_invitation,
                referral_replenishment = referral_replenishment
            )
            .returning(NotificationSettings)
        )
        await session_db.commit()
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
        action_type="deleted ban account",
        details={'message': "Удалил аккаунт из забаненных", "user_id": user_id}
    )

    async with get_db() as session_db:
        await session_db.execute(delete(BannedAccounts).where(BannedAccounts.user_id == user_id))
        session_db.add(new_admin_log)
        await session_db.commit()

    async with get_redis() as session_redis:
        await session_redis.delete(f"banned_account:{user_id}")

    await send_log(
        f"#Аккаунт_разбанен \n\n"
        f"Админ c ID = '{admin_id}' разбанил пользователя \n"
        f"ID разбаненного аккаунта: '{user_id}'"
    )
