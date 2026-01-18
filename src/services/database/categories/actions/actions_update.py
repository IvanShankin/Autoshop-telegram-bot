import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from src.exceptions import AccountCategoryNotFound, TheCategoryStorageAccount, \
    IncorrectedNumberButton, IncorrectedCostPrice, IncorrectedAmountSale, CategoryStoresSubcategories
from src.services.database.categories.models import AccountStorage, TgAccountMedia
from src.services.database.categories.models.main_category_and_product import ProductType
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.system.actions import create_ui_image, delete_ui_image
from src.services.redis.filling import filling_all_keys_category, filling_product_account_by_account_id, \
    filling_sold_account_by_account_id, filling_sold_accounts_by_owner_id
from src.services.database.core.database import get_db
from src.services.database.categories.models import Categories, ProductAccounts, \
    CategoryTranslation, CategoryFull


async def update_category(
        category_id: int,
        index: int = None,
        show: bool = None,
        file_data: bytes = None,
        number_buttons_in_row: int = None,
        is_product_storage: bool = None,
        allow_multiple_purchase: bool = None,
        price: int = None,
        cost_price: int = None,
        product_type: ProductType | None = None,
        type_account_service: AccountServiceType | None = None,
) -> Categories:
    """
    :param file_data: поток байтов для создания нового ui_image, старый будет удалён
    :except IncorrectedAmountSale: Цена аккаунтов должна быть положительным числом или равно 0
    :except IncorrectedCostPrice: Себестоимость аккаунтов должна быть положительным числом
    :except IncorrectedNumberButton: Количество кнопок в строке, должно быть в диапазоне от 1 до 8
    :except AccountCategoryNotFound: Категория аккаунтов не найдена
    :except TheCategoryStorageAccount: Категория хранит аккаунты.
    :except CategoryStoresSubcategories: Категория хранит подкатегории.
    Необходимо извлечь их для применения изменений
    """
    if price is not None and price <= 0:
        raise IncorrectedAmountSale("Цена товара должна быть положительным числом")
    if cost_price is not None and cost_price < 0:
        raise IncorrectedCostPrice("Себестоимость товара должна быть положительным числом")
    if number_buttons_in_row is not None and (number_buttons_in_row < 1 or number_buttons_in_row > 8):
        raise IncorrectedNumberButton("Количество кнопок в строке, должно быть в диапазоне от 1 до 8")

    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(Categories)
            .options(selectinload(Categories.ui_image))
            .where(Categories.category_id == category_id)
        )
        category: Categories = result.scalar_one_or_none()
        old_ui_image = category.ui_image_key
        if not category:
            raise AccountCategoryNotFound(f"Категория с id = {category_id} не найдена")

        # собираем только те поля, которые реально переданы
        update_data = {}
        if is_product_storage is not None:
            if is_product_storage: # если хотим установить хранилище аккаунтов
                result = await session.execute(
                    select(Categories).where(Categories.parent_id == category_id)
                )
                subcategories: Categories = result.scalars().first()
                if subcategories:  # если данная категория хранит подкатегории
                    raise CategoryStoresSubcategories(
                        f"Категория с id = {category_id} хранит подкатегории. Сперва удалите их"
                    )

                if not product_type:
                    raise ValueError("При установки хранилища необходимо указать тип продукта 'product_type'")

                if product_type == ProductType.ACCOUNT and not type_account_service:
                    raise ValueError(
                        "При установки хранилища аккаунтов необходимо указать тип сервиса аккаунтов 'type_account_service'"
                    )
            else: # если хотим убрать хранилище аккаунтов
                result = await session.execute(
                    select(ProductAccounts).where(ProductAccounts.category_id == category_id)
                )
                product_account: ProductAccounts = result.scalars().first()
                if product_account: # если данная категория хранит аккаунты
                    raise TheCategoryStorageAccount(
                        f"Категория с id = {category_id} хранит товары. "
                        f"Необходимо извлечь их для применения изменений"
                    )


            update_data["is_product_storage"] = is_product_storage
        if allow_multiple_purchase is not None:
            update_data["allow_multiple_purchase"] = allow_multiple_purchase
        if show is not None:
            update_data["show"] = show
        if price is not None:
            update_data["price"] = price
        if cost_price is not None:
            update_data["cost_price"] = cost_price
        if number_buttons_in_row is not None:
            update_data["number_buttons_in_row"] = number_buttons_in_row
        if product_type is not None:
            update_data["product_type"] = product_type
        if type_account_service is not None:
            update_data["type_account_service"] = type_account_service
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
            total_res = await session.execute(select(func.count()).select_from(Categories))
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
                        update(Categories)
                        .where(Categories.index >= new_index)
                        .where(Categories.index < old_index)
                        .values(index=Categories.index + 1)
                    )
                else:
                    # Перемещение вниз: сдвигаем все записи между [old_index+1, new_index] вниз (-1)
                    await session.execute(
                        update(Categories)
                        .where(Categories.index <= new_index)
                        .where(Categories.index > old_index)
                        .values(index=Categories.index - 1)
                    )

                update_data["index"] = new_index

        if update_data:
            await session.execute(
                update(Categories)
                .where(Categories.category_id == category_id)
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
        await filling_all_keys_category()

    return category


async def update_category_translation(
        category_id: int,
        language: str,
        name: str = None,
        description: str = None
) -> CategoryFull:
    """
    :except AccountCategoryNotFound: Категория с id = {category_id} не найдена
    """
    async with get_db() as session:
        # загружаем текущий объект
        result = await session.execute(
            select(Categories).where(Categories.category_id == category_id)
        )
        category: Categories = result.scalar_one_or_none()
        if not category:
            raise AccountCategoryNotFound(f"Категория с id = {category_id} не найдена")

        result = await session.execute(
            select(CategoryTranslation)
            .where(
                (CategoryTranslation.category_id == category_id) &
                (CategoryTranslation.lang == language)
            )
        )
        translation: CategoryTranslation = result.scalar_one_or_none()
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
                update(CategoryTranslation)
                .where(
                    (CategoryTranslation.category_id == category_id) &
                    (CategoryTranslation.lang == language)
                )
                .values(**update_data)
            )

            await session.commit()

            # обновляем объект в памяти (чтобы вернуть актуальные данные)
            for key, value in update_data.items():
                setattr(translation, key, value)

    if update_data:
        # обновит redis с новыми index
        await filling_all_keys_category(category_id=category_id)

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

        update_data = {}
        if storage_uuid is not None:
            update_data['storage_uuid'] = storage_uuid
        if file_path is not None:
            update_data['file_path'] = file_path
        if checksum is not None:
            update_data['checksum'] = checksum
        if status is not None:
            update_data['status'] = status
        if encrypted_key is not None:
            update_data['encrypted_key'] = encrypted_key
        if encrypted_key_nonce is not None:
            update_data['encrypted_key_nonce'] = encrypted_key_nonce
        if key_version is not None:
            update_data['key_version'] = key_version
        if encryption_algo is not None:
            update_data['encryption_algo'] = encryption_algo
        if login_encrypted is not None:
            update_data['login_encrypted'] = login_encrypted
        if password_encrypted is not None:
            update_data['password_encrypted'] = password_encrypted
        if last_check_at is not None:
            update_data['last_check_at'] = last_check_at
        if is_valid is not None:
            update_data['is_valid'] = is_valid
        if is_active is not None:
            update_data['is_active'] = is_active

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
        update_data = {}
        if tdata_tg_id is not None:
            update_data['tdata_tg_id'] = tdata_tg_id
        if session_tg_id is not None:
            update_data['session_tg_id'] = session_tg_id

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


