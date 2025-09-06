import orjson
from dateutil.parser import parse
from sqlalchemy import select, update

from src.bot_instance import bot
from src.database.core_models import Users, Settings
from src.database.database import get_db
from src.database.filling_database import filling_settings
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.time_storage import TIME_USER


async def get_settings() -> Settings:
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f'settings')
        if redis_data:
            data = orjson.loads(redis_data)
            settings = Settings(
                support_username=data['support_username'],
                hash_token_accountant_bot=data['hash_token_accountant_bot'],
                channel_for_logging_id=data['channel_for_logging_id'],
                channel_for_subscription_id=data['channel_for_subscription_id'],
                FAQ=data['FAQ']
            )
            return settings

        async with get_db() as session_db:
            result_db = await session_db.execute(select(Settings))
            settings_db = result_db.scalars().first()
            if settings_db:
                async with get_redis() as session_redis:
                    await session_redis.set(f'settings', orjson.dumps(settings_db.to_dict()))
                return settings_db
            else:
                await filling_settings()
                return await get_settings()

async def update_settings(settings: Settings) -> Settings:
    """
    Обновляет настройки в БД и Redis.
    :param Settings Объект настроек с обновленными данными
    """
    # Обновляем в БД
    async with get_db() as session_db:
        # Выполняем обновление
        await session_db.execute(
            update(Settings)
            .values(
                support_username=settings.support_username,
                hash_token_accountant_bot=settings.hash_token_accountant_bot,
                channel_for_logging_id=settings.channel_for_logging_id,
                channel_for_subscription_id=settings.channel_for_subscription_id,
                FAQ=settings.FAQ,
            )
        )
        await session_db.commit()

    # Обновляем в Redis
    async with get_redis() as session_redis:
        await session_redis.set(
            f'settings',
            orjson.dumps(settings.to_dict())
        )
    return settings

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


