import uuid
from datetime import datetime
from typing import Literal, Any, List

import orjson
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from src.services.database.selling_accounts.models.models import AccountStorage, TgAccountMedia
from src.services.database.system.actions import create_ui_image, delete_ui_image
from src.services.redis.core_redis import get_redis
from src.services.redis.filling_redis import filling_all_account_services, filling_account_categories_by_service_id, \
    filling_account_categories_by_category_id, filling_account_services, filling_product_account_by_account_id, \
    filling_product_accounts_by_category_id, filling_sold_account_by_account_id, filling_sold_accounts_by_owner_id
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.models import AccountServices, AccountCategories, ProductAccounts, \
    AccountCategoryTranslation, AccountCategoryFull


def _create_dict(data: List[tuple[str, Any]]) -> dict:
    """
    Формирует словарь, если переменная есть, то запишет её с указанным ключом
    :param data: List[("имя для ключа", значение)]
    """
    result = {}
    for key_name, value in data:
        if value is not None:
            result[key_name] = value
    return result


async def update_account_service(
        account_service_id: int,
        name: str = None,
        index: int = None,
        show: bool = None
) -> AccountServices:
    """Можно изменить всё кроме типа сервиса"""
    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(AccountServices).where(AccountServices.account_service_id == account_service_id)
        )
        service: AccountServices = result.scalar_one_or_none()
        if not service:
            raise ValueError(f"Сервис аккаунтов с id = {account_service_id} не найден")

        # собираем только те поля, которые реально переданы
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if show is not None:
            update_data["show"] = show
        if index is not None:
            # нормализуем new_index — int, не меньше 0
            try:
                new_index = int(index)
            except Exception:
                raise ValueError("index должен быть целым числом")
            if new_index < 0:
                new_index = 0

            # считаем сколько всего записей (чтобы определить максимальный индекс)
            total_res = await session.execute(select(func.count()).select_from(AccountServices))
            total_count = total_res.scalar_one()
            # max_index — индекс последнего элемента в текущей коллекции
            max_index = max(0, total_count - 1)

            # если новый индекс больше максимального — помещаем в конец
            if new_index > max_index:
                new_index = max_index

            # старый индекс — если None, считаем как "последний" (т.е. append)
            old_index = service.index if service.index is not None else max_index

            # если фактически ничего не меняется — пропускаем перестановки
            if new_index != old_index:
                # сдвиги других записей в зависимости от направления перемещения
                if new_index < old_index:
                    # перемещение влево (меньше): поднимаем (+1) все записи с индексом в [new_index, old_index-1]
                    await session.execute(
                        update(AccountServices)
                        .where(AccountServices.index >= new_index)
                        .where(AccountServices.index < old_index)
                        .values(index=AccountServices.index + 1)
                    )
                else:  # new_index > old_index
                    # перемещение вправо (больше): опускаем (-1) все записи с индексом в [old_index+1, new_index]
                    await session.execute(
                        update(AccountServices)
                        .where(AccountServices.index <= new_index)
                        .where(AccountServices.index > old_index)
                        .values(index=AccountServices.index - 1)
                    )

                update_data["index"] = new_index
            # else: new_index == old_index -> ничего не делаем по индексам

        if update_data:
            await session.execute(
                update(AccountServices)
                .where(AccountServices.account_service_id == account_service_id)
                .values(**update_data)
            )

            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(service, key, value)

        if update_data:
            await session.execute(
                update(AccountServices)
                .where(AccountServices.account_service_id == account_service_id)
                .values(**update_data)
            )

            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(service, key, value)

    if update_data:
        await filling_all_account_services() # обновляем redis для поддержания целостности индексов

        if index is None: # если индекс не меняли, то достаточно обновить только один ключ в redis
            async with get_redis() as session_redis:
                await session_redis.set(f"account_service:{account_service_id}", orjson.dumps(service.to_dict()))
        else:
            await filling_account_services()

    return service


async def update_account_category(
        account_category_id: int,
        index: int = None,
        show: bool = None,
        file_data: bytes = None,
        number_buttons_in_row: int = None,
        is_accounts_storage: bool = None,
        price_one_account: int = None,
        cost_price_one_account: int = None,
) -> AccountCategories:
    """:param file_data: поток байтов для создания нового ui_image, старый будет удалён"""
    if price_one_account is not None and price_one_account <= 0:
        raise ValueError("Цена аккаунтов должна быть положительным числом")
    if cost_price_one_account is not None  and cost_price_one_account < 0:
        raise ValueError("Себестоимость аккаунтов должна быть положительным числом")
    if number_buttons_in_row is not None and (number_buttons_in_row < 1 or number_buttons_in_row > 8):
        raise ValueError("Количество кнопок в строке, должно быть в диапазоне от 1 до 8")

    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(AccountCategories)
            .options(selectinload(AccountCategories.ui_image))
            .where(AccountCategories.account_category_id == account_category_id)
        )
        category: AccountCategories = result.scalar_one_or_none()
        old_ui_image = category.ui_image_key
        if not category:
            raise ValueError(f"Категория аккаунтов с id = {account_category_id} не найдена")

        # собираем только те поля, которые реально переданы
        update_data = {}
        if is_accounts_storage is not None:
            if category.is_accounts_storage:
                result = await session.execute(
                    select(ProductAccounts).where(ProductAccounts.account_category_id == account_category_id)
                )
                product_account: ProductAccounts = result.scalars().first()
                if product_account: # если данная категория хранит аккаунты
                    raise ValueError(
                        f"Категория с id = {account_category_id} хранит аккаунты. "
                        f"Необходимо извлечь их для применения изменений"
                    )

            update_data["is_accounts_storage"] = is_accounts_storage
        if show is not None:
            update_data["show"] = show
        if price_one_account is not None:
            update_data["price_one_account"] = price_one_account
        if cost_price_one_account is not None:
            update_data["cost_price_one_account"] = cost_price_one_account
        if number_buttons_in_row is not None:
            update_data["number_buttons_in_row"] = number_buttons_in_row
        if file_data is not None:
            ui_image = await create_ui_image(
                key=str(uuid.uuid4()),
                file_data=file_data,
                show=category.ui_image.show if category.ui_image else True
            )
            update_data["ui_image_key"] = ui_image.key
        if index is not None:
            try:
                new_index = int(index)
            except Exception:
                raise ValueError("index должен быть целым числом")

            # индексы не могут быть отрицательными
            if new_index < 0:
                new_index = 0

            # определяем общее количество категорий
            total_res = await session.execute(select(func.count()).select_from(AccountCategories))
            total_count = total_res.scalar_one()
            max_index = max(0, total_count - 1)

            # если новый индекс больше максимально допустимого — ставим в конец
            if new_index > max_index:
                new_index = max_index

            # если старый индекс None — считаем, что был в конце
            old_index = category.index if category.index is not None else max_index

            # если индекс действительно меняется
            if new_index != old_index:
                if new_index < old_index:
                    # Перемещение вверх: сдвигаем все записи между [new_index, old_index-1] вверх (+1)
                    await session.execute(
                        update(AccountCategories)
                        .where(AccountCategories.index >= new_index)
                        .where(AccountCategories.index < old_index)
                        .values(index=AccountCategories.index + 1)
                    )
                else:
                    # Перемещение вниз: сдвигаем все записи между [old_index+1, new_index] вниз (-1)
                    await session.execute(
                        update(AccountCategories)
                        .where(AccountCategories.index <= new_index)
                        .where(AccountCategories.index > old_index)
                        .values(index=AccountCategories.index - 1)
                    )

                update_data["index"] = new_index

        if update_data:
            await session.execute(
                update(AccountCategories)
                .where(AccountCategories.account_category_id == account_category_id)
                .values(**update_data)
            )

            await session.commit()

            if file_data is not None and category.ui_image: # удаление прошлого изображения
                await delete_ui_image(old_ui_image)

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(category, key, value)

    if update_data:
        # обновит redis с новыми index
        await filling_account_categories_by_service_id()
        await filling_account_categories_by_category_id()

    return category


async def update_account_category_translation(
        account_category_id: int,
        language: str,
        name: str = None,
        description: str = None
) -> AccountCategoryFull:
    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(AccountCategories).where(AccountCategories.account_category_id == account_category_id)
        )
        category: AccountCategories = result.scalar_one_or_none()
        if not category:
            raise ValueError(f"Категория аккаунтов с id = {account_category_id} не найдена")

        result = await session.execute(
            select(AccountCategoryTranslation)
            .where(
                (AccountCategoryTranslation.account_category_id == account_category_id) &
                (AccountCategoryTranslation.lang == language)
            )
        )
        translation: AccountCategoryTranslation = result.scalar_one_or_none()
        if not translation:
            raise ValueError(f"Перевод с языком '{language}' не найден")

        # собираем поля которые передали
        update_data = {}
        if name is not None:
            update_data['name'] = name
        if description is not None:
            update_data['description'] = description

        if update_data:
            await session.execute(
                update(AccountCategoryTranslation)
                .where(
                    (AccountCategoryTranslation.account_category_id == account_category_id) &
                    (AccountCategoryTranslation.lang == language)
                )
                .values(**update_data)
            )

            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(translation, key, value)

    if update_data:
        # обновит redis с новыми index
        await filling_account_categories_by_service_id()
        await filling_account_categories_by_category_id()

    return translation


async def update_account_storage(
    account_storage_id: int = None,
    storage_uuid: str = None,
    file_path: str = None,
    checksum: str = None,
    status: Literal["for_sale", "bought", "deleted"] = None,
    encrypted_key: str = None,
    encrypted_key_nonce: str = None,
    key_version: int = None,
    encryption_algo: str = None,
    login_encrypted: str = None,
    password_encrypted: str = None,
    last_check_at: datetime = None,
    is_valid: bool = None,
    is_active: bool = None,
) -> AccountStorage:
    async with get_db() as session:
        result = await session.execute(
            select(AccountStorage)
            .options(
                selectinload(AccountStorage.product_account),
                selectinload(AccountStorage.sold_account),
                selectinload(AccountStorage.deleted_account)
            )
            .where(AccountStorage.account_storage_id == account_storage_id)
        )
        account: AccountStorage = result.scalar_one_or_none()

        update_data = _create_dict([
            ('storage_uuid', storage_uuid),
            ('file_path', file_path),
            ('checksum', checksum),
            ('status', status),
            ('encrypted_key', encrypted_key),
            ('encrypted_key_nonce', encrypted_key_nonce),
            ('key_version', key_version),
            ('encryption_algo', encryption_algo),
            ('login_encrypted', login_encrypted),
            ('password_encrypted', password_encrypted),
            ('last_check_at', last_check_at),
            ('is_valid', is_valid),
            ('is_active', is_active),
        ])

        if update_data:
            await session.execute(
                update(AccountStorage)
                .where(AccountStorage.account_storage_id == account_storage_id)
                .values(**update_data)
            )
            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(account, key, value)

        # один AccountStorage - одна запись в другой таблице, но будем заполнять везде где есть
        if account.product_account:
            await filling_product_account_by_account_id(account.product_account.account_id)
            await filling_product_accounts_by_category_id()
        if account.sold_account:
            await filling_sold_account_by_account_id(account.sold_account.sold_account_id)
            await filling_sold_accounts_by_owner_id(account.sold_account.owner_id)

        return account

async def update_tg_account_media(
        tg_account_media_id: int,
        tdata_tg_id: str = None,
        session_tg_id: str = None
) -> TgAccountMedia | None:
    async with get_db() as session:
        update_data = _create_dict([
            ('tdata_tg_id', tdata_tg_id),
            ('session_tg_id', session_tg_id),
        ])

        if update_data:
            result = await session.execute(
                update(TgAccountMedia)
                .where(TgAccountMedia.tg_account_media_id == tg_account_media_id)
                .values(**update_data)
                .returning(TgAccountMedia)
            )
            tg_account_media = result.scalar_one_or_none()
            await session.commit()
            return tg_account_media


