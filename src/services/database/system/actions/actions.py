from datetime import datetime, UTC, timedelta
import os
from pathlib import Path
from typing import List

import aiofiles
import orjson
from sqlalchemy import select, update, delete, func, desc

from src.config import get_config
from src.services.database.categories.models import PurchasesAccounts, ProductAccounts, Categories
from src.services.database.system.shemas.shemas import StatisticsData, ReplenishmentPaymentSystem
from src.services.database.users.models import Users, Replenishments
from src.services.redis.filling_redis import filling_types_payments_by_id, filling_all_types_payments, \
    filling_ui_image
from src.services.redis.time_storage import TIME_SETTINGS
from src.services.database.system.models import Settings, TypePayments, BackupLogs
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis
from src.services.database.system.models import UiImages
from src.utils.ui_images_data import get_ui_images, UI_IMAGES_IGNORE_ADMIN


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
            return None


async def update_settings(
    maintenance_mode: bool = None,
    support_username: str = None,
    channel_for_logging_id: int = None,
    channel_for_subscription_id: int = None,
    channel_for_subscription_url: str = None,
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
    if channel_for_subscription_url is not None:
        update_data["channel_for_subscription_url"] = channel_for_subscription_url
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


async def get_ui_images_by_page(page: int, page_size: int = None) -> List[str]:
    # Получаем все ключи, исключив админские
    if not page_size:
        page_size = get_config().different.page_size

    filtered_keys = [
        key for key in get_ui_images().keys()
        if key not in UI_IMAGES_IGNORE_ADMIN
    ]

    # Считаем границы страницы
    start = (page - 1) * page_size
    end = start + page_size

    # Возвращаем ключи нужной страницы
    return filtered_keys[start:end]


async def create_ui_image(key: str, file_data: bytes, show: bool = True, file_id: str = None) -> UiImages:
    """
    Сохраняет файл локально с именем в аргументе "key" и создаёт запись в БД UiImages.

    :param key: Уникальный ключ изображения (например: 'main_menu_banner')
    :param file_data: Содержимое файла в виде байтов
    :param show: Флаг отображения
    :param file_id: id в телеграмме
    :return:
    """
    new_path = get_config().paths.ui_sections_dir / f"{key}.png"
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
            await update_ui_image(key=key, show=ui_image.show, file_id=file_id)
            return ui_image
        else:
            # Иначе создаём новую запись
            async with aiofiles.open(new_path, "wb") as f:
                await f.write(file_data)

            ui_image = UiImages(
                key=key,
                file_path=str(new_path),
                file_id=file_id,
                show=show,
            )
            session_db.add(ui_image)
            await session_db.commit()

        await filling_ui_image(key) # обновление redis
        return ui_image


async def get_all_ui_images() -> List[UiImages] | None:
    """Вернёт все записи в таблице UiImage"""
    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages))
        return result_db.scalars().all()


async def get_ui_image(key: str) -> UiImages | None:
    """Если есть данные по данному ключу, то вернёт UiImages по данному ключу, если нет, то вернёт None"""
    async with get_redis() as session_redis:
        result_redis = await session_redis.get(f'ui_image:{key}')
        if result_redis:
            ui_image_dict = orjson.loads(result_redis)
            return UiImages(**ui_image_dict)

    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages).where(UiImages.key == key))
        ui_image = result_db.scalar_one_or_none()
        return ui_image


async def update_ui_image(key: str, show: bool = None, file_id: str | None = None) -> UiImages | None:
    update_data = {}
    if show is not None:
        update_data["show"] = show
    if file_id is not None:
        update_data["file_id"] = file_id

    if update_data:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                update(UiImages)
                .where(UiImages.key == key)
                .values(**update_data)
                .returning(UiImages)
            )
            result = result_db.scalar_one_or_none()
            await session_db.commit()
            if result:
                await filling_ui_image(key) # обновление redis
            return result
    return None


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


async def add_backup_log(
    storage_file_name: str,
    storage_encrypted_dek_name: str,
    encrypted_dek_b64: str,
    dek_nonce_b64: str,
    size_bytes: int
) -> BackupLogs:
    new_backup_log = BackupLogs(
        storage_file_name = storage_file_name,
        storage_encrypted_dek_name = storage_encrypted_dek_name,
        encrypted_dek_b64 = encrypted_dek_b64,
        dek_nonce_b64 = dek_nonce_b64,
        size_bytes = size_bytes,
    )
    async with get_db() as session_db:
        session_db.add(new_backup_log)
        await session_db.commit()
        await session_db.refresh(new_backup_log)

    return new_backup_log


async def get_backup_log_by_id(
    backup_log_id: int
) -> BackupLogs:
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(BackupLogs)
            .where(BackupLogs.backup_log_id == backup_log_id)
        )
        return result_db.scalar_one_or_none()


async def get_all_backup_logs_desc() -> List[BackupLogs]:
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(BackupLogs).order_by(BackupLogs.created_at.desc())
        )
        return result_db.scalars().all()


async def delete_backup_log(backup_log_id: int):
    async with get_db() as session_db:
        await session_db.execute(
            delete(BackupLogs)
            .where(BackupLogs.backup_log_id == backup_log_id)
        )
        await session_db.commit()


async def get_statistics(interval_days: int) -> StatisticsData:
    up_to_date = datetime.now(UTC) - timedelta(days=interval_days)

    async with get_db() as session_db:
        result_db = await session_db.execute(select(func.count()).where(Users.last_used >= up_to_date))
        active_users = result_db.scalar()

        result_db = await session_db.execute(select(func.count()).where(Users.created_at >= up_to_date))
        new_users = result_db.scalar()

        result_db = await session_db.execute(select(func.count()).select_from(Users))
        total_users = result_db.scalar()

        result_db = await session_db.execute(select(PurchasesAccounts).where(PurchasesAccounts.purchase_date >= up_to_date))
        needs_sale_accounts: List[PurchasesAccounts] = result_db.scalars().all()

        quantity_sale_accounts = max(len(needs_sale_accounts), 0)

        amount_sale_accounts = 0
        for sale_acc in needs_sale_accounts:
            amount_sale_accounts += sale_acc.purchase_price

        total_net_profit = 0
        for sale_acc in needs_sale_accounts:
            total_net_profit += sale_acc.net_profit

        result_db = await session_db.execute(select(Replenishments).where(Replenishments.created_at >= up_to_date))
        needs_replenishments: List[Replenishments] = result_db.scalars().all()

        quantity_replenishments = max(len(needs_replenishments), 0)
        amount_replenishments = 0
        for replenishment in needs_replenishments:
            amount_replenishments += replenishment.amount

        all_type_payments = await get_all_types_payments()
        replenishment_payment_systems = []
        for type_payment in all_type_payments:
            replenishments = [
                replenishment
                for replenishment in needs_replenishments
                if replenishment.type_payment_id == type_payment.type_payment_id
            ]

            amount_replenishments_current_type = 0
            for replenishment in replenishments:
                amount_replenishments_current_type += replenishment.amount

            replenishment_payment_systems.append(
                ReplenishmentPaymentSystem(
                    name = type_payment.name_for_user,
                    quantity_replenishments = max(len(replenishments), 0),
                    amount_replenishments = amount_replenishments_current_type
                )
            )


        result = await session_db.execute(
            select(func.coalesce(func.sum(Categories.price), 0))
            .select_from(ProductAccounts)
            .join(ProductAccounts.category)
        )
        funds_in_bot = result.scalar()

        result_db = await session_db.execute(select(func.count()).select_from(ProductAccounts))
        accounts_for_sale = result_db.scalar()

        result_db = await session_db.execute(select(BackupLogs.created_at).order_by(desc(BackupLogs.created_at)).limit(1))
        last_backup = result_db.scalar_one_or_none()

        last_backup = last_backup if last_backup else "—"

    return StatisticsData(
        active_users=active_users,
        new_users=new_users,
        total_users=total_users,
        quantity_sale_accounts=quantity_sale_accounts,
        amount_sale_accounts=amount_sale_accounts,
        total_net_profit=total_net_profit,
        quantity_replenishments=quantity_replenishments,
        amount_replenishments=amount_replenishments,
        replenishment_payment_systems=replenishment_payment_systems,
        funds_in_bot=funds_in_bot,
        accounts_for_sale=accounts_for_sale,
        last_backup=last_backup,
    )
