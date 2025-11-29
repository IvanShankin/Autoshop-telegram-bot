import os
import shutil
from pathlib import Path
from typing import List

import aiofiles
import orjson
from sqlalchemy import select, update, delete, func

from src.services.redis.filling_redis import filling_types_payments_by_id, filling_all_types_payments, \
    filling_ui_image
from src.services.redis.time_storage import TIME_SETTINGS
from src.services.database.system.models import Settings, TypePayments, BackupLogs
from src.services.database.core.database import get_db
from src.services.database.core.filling_database import filling_settings
from src.services.redis.core_redis import get_redis
from src.services.database.system.models import UiImages
from src.utils.ui_images_data import UI_SECTIONS


def _check_file_exists(ui_image: UiImages) -> UiImages | None:
    return ui_image if os.path.exists(ui_image.file_path) else None


async def get_settings() -> Settings:
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f'settings')
        if redis_data:
            data = orjson.loads(redis_data)
            settings = Settings(**data)
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


async def update_settings(
    maintenance_mode: bool = None,
    support_username: str = None,
    channel_for_logging_id: int = None,
    channel_for_subscription_id: int = None,
    shop_name: str = None,
    channel_name: str = None,
    faq: str = None,
) -> Settings | None:
    """
    Обновляет настройки в БД и Redis.
    """
    update_data = {}
    if maintenance_mode is not None:
        update_data["maintenance_mode"] = maintenance_mode
    if support_username is not None:
        update_data["support_username"] = support_username
    if channel_for_logging_id is not None:
        update_data["channel_for_logging_id"] = channel_for_logging_id
    if channel_for_subscription_id is not None:
        update_data["channel_for_subscription_id"] = channel_for_subscription_id
    if shop_name is not None:
        update_data["shop_name"] = shop_name
    if channel_name is not None:
        update_data["channel_name"] = channel_name
    if faq is not None:
        update_data["FAQ"] = faq

    if update_data:
        # Обновляем в БД
        async with get_db() as session_db:
            # Выполняем обновление
            result_db = await session_db.execute(update(Settings).values(**update_data).returning(Settings))
            settings = result_db.scalars().first()
            await session_db.commit()

        # Обновляем в Redis
        async with get_redis() as session_redis:
            await session_redis.set(
                f'settings',
                orjson.dumps(settings.to_dict())
            )
        return settings
    return None


async def create_ui_image(key: str, file_data: bytes, show: bool = True) -> UiImages:
    """
    Сохраняет файл локально с именем в аргументе "key" и создаёт запись в БД UiImages.

    :param key: Уникальный ключ изображения (например: 'main_menu_banner')
    :param file_data: Содержимое файла в виде байтов
    :param show: Флаг отображения
    :return:
    """
    new_path = UI_SECTIONS / f"{key}.png"
    new_path.parent.mkdir(parents=True, exist_ok=True) # создаём директорию, если её нет

    async with get_db() as session_db:
        result = await session_db.execute(select(UiImages).where(UiImages.key == key))
        ui_image = result.scalar_one_or_none()

        if ui_image:
            # Перезаписываем файл, но не создаём новую запись
            async with aiofiles.open(new_path, "wb") as f:
                await f.write(file_data)
            ui_image.file_path = str(new_path)
            await session_db.commit()
            await update_ui_image(key=key, show=ui_image.show, file_id=None)
            return ui_image
        else:
            # Иначе создаём новую запись
            async with aiofiles.open(new_path, "wb") as f:
                await f.write(file_data)

            ui_image = UiImages(
                key=key,
                file_path=str(new_path),
                show=show,
            )
            session_db.add(ui_image)
            await session_db.commit()

        await filling_ui_image(key) # обновление redis
        return ui_image


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
    """Вернёт все записи в таблице UiImage"""
    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages))
        return result_db.scalars().all()


async def update_ui_image(key: str, show: bool, file_id: str | None = None) -> UiImages | None:
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


async def delete_ui_image(key: str) -> UiImages | None:
    """
    Удалит UiImage с БД и redis, удалит связанный с ним файл.
    :return: Удалённый объект (если удалили)
    """
    async with get_db() as session_db:
        result = await session_db.execute(
            delete(UiImages)
            .where(UiImages.key == key)
            .returning(UiImages)
        )
        deleted_ui_image: UiImages = result.scalar_one_or_none()
        await session_db.commit()

        if deleted_ui_image and deleted_ui_image.file_path:
            # можно не проверять его существование
            Path(deleted_ui_image.file_path).unlink(missing_ok=True)

    async with get_redis() as session_redis:
        await session_redis.delete(f'ui_image:{key}')

    return deleted_ui_image


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
        await filling_all_types_payments()
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

    update_data = {}

    if name_for_user is not None:
        update_data['name_for_user'] = name_for_user
    if is_active is not None:
        update_data['is_active'] = is_active
    if commission is not None:
        update_data['commission'] = commission
    if index is not None:
        async with get_db() as session_db:
            # нормализуем new_index — int, не меньше 0
            try:
                new_index = int(index)
            except Exception:
                raise ValueError("index должен быть целым числом")
            if new_index < 0:
                new_index = 0

            # считаем сколько всего записей (чтобы определить максимальный индекс)
            total_res = await session_db.execute(select(func.count()).select_from(TypePayments))
            total_count = total_res.scalar_one()
            # max_index — индекс последнего элемента в текущей коллекции
            max_index = max(0, total_count - 1)

            # если новый индекс больше максимального — помещаем в конец
            if new_index > max_index:
                new_index = max_index

            # старый индекс — если None, считаем как "последний" (т.е. append)
            old_index = type_payment.index if type_payment.index is not None else max_index

            # если фактически ничего не меняется — пропускаем перестановки
            if new_index != old_index:
                # сдвиги других записей в зависимости от направления перемещения
                if new_index < old_index:
                    # перемещение влево (меньше): поднимаем (+1) все записи с индексом в [new_index, old_index-1]
                    await session_db.execute(
                        update(TypePayments)
                        .where(TypePayments.index >= new_index)
                        .where(TypePayments.index < old_index)
                        .values(index=TypePayments.index + 1)
                    )
                else:  # new_index > old_index
                    # перемещение вправо (больше): опускаем (-1) все записи с индексом в [old_index+1, new_index]
                    await session_db.execute(
                        update(TypePayments)
                        .where(TypePayments.index <= new_index)
                        .where(TypePayments.index > old_index)
                        .values(index=TypePayments.index - 1)
                    )

                await session_db.commit()

                update_data["index"] = new_index
            # else: new_index == old_index -> ничего не делаем по индексам

    if extra_data is not None:
        update_data["extra_data"] = extra_data

    if update_data:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                update(TypePayments)
                .where(TypePayments.type_payment_id==type_payment_id)
                .values(**update_data)
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

