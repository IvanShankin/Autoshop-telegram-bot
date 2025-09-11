import orjson
from sqlalchemy import select, update

from src.services.system.models import Settings
from src.services.database.database import get_db
from src.services.database.filling_database import filling_settings
from src.redis_dependencies.core_redis import get_redis

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