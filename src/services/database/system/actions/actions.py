import os
from typing import List

import orjson
from sqlalchemy import select, update

from src.config import MEDIA_DIR
from src.services.redis.filling_redis import filling_types_payments_by_id, filling_all_types_payments, \
    filling_ui_image
from src.services.redis.time_storage import TIME_SETTINGS
from src.services.database.system.models import Settings, TypePayments, BackupLogs
from src.services.database.core.database import get_db
from src.services.database.core.filling_database import filling_settings
from src.services.redis.core_redis import get_redis
from src.services.database.system.models import UiImages


def _check_file_exists(ui_image: UiImages) -> UiImages | None:
    return ui_image if os.path.exists(ui_image.file_path) else None

async def get_settings() -> Settings:
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f'settings')
        if redis_data:
            data = orjson.loads(redis_data)
            settings = Settings(
                support_username=data['support_username'],
                maintenance_mode =data['maintenance_mode'],
                channel_for_logging_id=data['channel_for_logging_id'],
                channel_for_subscription_id=data['channel_for_subscription_id'],
                shop_name=data['shop_name'],
                channel_name=data['channel_name'],
                linc_info_ref_system=data['linc_info_ref_system'],
                FAQ=data['FAQ']
            )
            return settings

        async with get_db() as session_db:
            result_db = await session_db.execute(select(Settings))
            settings_db = result_db.scalars().first()
            if settings_db:
                async with get_redis() as session_redis:
                    await session_redis.setex(f'settings', TIME_SETTINGS, orjson.dumps(settings_db.to_dict()))
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
                maintenance_mode =settings.maintenance_mode ,
                channel_for_logging_id=settings.channel_for_logging_id,
                channel_for_subscription_id=settings.channel_for_subscription_id,
                shop_name=settings.shop_name,
                channel_name=settings.channel_name,
                linc_info_ref_system=settings.linc_info_ref_system,
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

async def get_ui_image(key: str) -> UiImages | None:
    """Если есть файл по данному ключу, то вернёт UiImages по данному ключу, если нет или он невалидный, то вернёт None"""
    async with get_redis() as session_redis:
        result_redis = await session_redis.get(f'ui_image:{key}')
        if result_redis:
            ui_image_dict = orjson.loads(result_redis)
            ui_image = UiImages(**ui_image_dict)
            return _check_file_exists(ui_image)

    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages).where(UiImages.key == key))
        ui_image = result_db.scalar_one_or_none()
        if ui_image:
            return _check_file_exists(ui_image)
        return None

async def get_all_ui_images() -> List[UiImages] | None:
    """Вернёт все записи у таблице UiImage"""
    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages))
        return result_db.scalars().all()

async def update_ui_image(key: str, show: bool, file_id: str) -> UiImages | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(
            update(UiImages)
            .where(UiImages.key == key)
            .values(show=show, file_id=file_id)
            .returning(UiImages)
        )
        result = result_db.scalar_one_or_none()
        await session_db.commit()
        if result:
            await filling_ui_image(key) # обновление redis
        return result


async def get_all_types_payments() -> List[TypePayments]:
    """Вернёт список всех типов платежей. Возвращает так же неактивные (is_active = False)!"""
    async with get_redis() as session_redis:
        result_redis = await session_redis.get('all_types_payments')
        if result_redis:
            types_payments_dict: list[dict] = orjson.loads(result_redis)
            if types_payments_dict:
                return [TypePayments( **type_payment ) for type_payment in types_payments_dict]

    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypePayments).order_by(TypePayments.index.asc()))
        return result_db.scalars().all()


async def get_type_payment(type_payment_id: int) -> TypePayments | None:
    """Вернёт тип платежа. Возвращает так же неактивный (is_active = False)!"""
    async with get_redis() as session_redis:
        result_redis = await session_redis.get(f'type_payments:{type_payment_id}')
        if result_redis:
            type_payment_dict = orjson.loads(result_redis)
            return TypePayments( **type_payment_dict )

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(TypePayments)
            .where(TypePayments.type_payment_id == type_payment_id)
        )
        type_payment = result_db.scalar_one_or_none()
        if type_payment:
            await filling_types_payments_by_id(type_payment_id)
        return type_payment

async def update_type_payment(
        type_payment_id: int,
        name_for_user: str = None,
        is_active: bool = None,
        commission: float = None,
        index: int = None,
        extra_data: dict = None
) -> TypePayments:
    type_payment = await get_type_payment(type_payment_id)
    if not type_payment:
        raise ValueError("Тип оплаты не найден")

    if name_for_user is None:
        name_for_user = type_payment.name_for_user
    if is_active is None:
        is_active = type_payment.is_active
    if commission is None:
        commission = type_payment.commission
    if index is None:
        index = type_payment.index
    else: # если необходимо изменить индекс
        async with get_db() as session_db:
            new_index = index
            old_index = type_payment.index

            # обновляем индексы
            if new_index < old_index:
                # сдвигаем все записи между new_index и old_index-1 вверх (+1)
                await session_db.execute(
                    update(TypePayments)
                    .where(TypePayments.index >= new_index)
                    .where(TypePayments.index < old_index)
                    .values(index=TypePayments.index + 1)
                )
            elif new_index > old_index:
                # сдвигаем все записи между old_index+1 и new_index вниз (-1)
                await session_db.execute(
                    update(TypePayments)
                    .where(TypePayments.index <= new_index)
                    .where(TypePayments.index > old_index)
                    .values(index=TypePayments.index - 1)
                )
            await session_db.commit()

    if extra_data is None:
        extra_data = type_payment.extra_data

    async with get_db() as session_db:
        result_db = await session_db.execute(
            update(TypePayments)
            .where(TypePayments.type_payment_id==type_payment_id)
            .values(
                name_for_user=name_for_user,
                is_active=is_active,
                commission=commission,
                index=index,
                extra_data=extra_data
            )
            .returning(TypePayments)
        )

        type_payment = result_db.scalar_one_or_none()
        await session_db.commit()

        # обновление redis
        await filling_all_types_payments()

        result_db = await session_db.execute(select(TypePayments))
        types_payments = result_db.scalars().all()
        for type_payment in types_payments:
            await filling_types_payments_by_id(type_payment.type_payment_id)

    return type_payment


async def add_backup_log(file_path: str, size_in_kilobytes: int) -> BackupLogs:
    new_backup_log = BackupLogs(
        file_path = file_path,
        size_in_kilobytes = size_in_kilobytes,
    )
    async with get_db() as session_db:
        session_db.add(new_backup_log)
        await session_db.commit()
        await session_db.refresh(new_backup_log)

    return new_backup_log

