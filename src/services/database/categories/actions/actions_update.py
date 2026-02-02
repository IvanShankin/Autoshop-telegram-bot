import uuid

from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from src.exceptions import AccountCategoryNotFound, TheCategoryStorageAccount, \
    IncorrectedNumberButton, IncorrectedCostPrice, IncorrectedAmountSale, CategoryStoresSubcategories, \
    TheCategoryStorageProducts
from src.services.database.categories.actions import get_quantity_products_in_category
from src.services.database.categories.models import Categories, ProductAccounts, \
    CategoryTranslation, CategoryFull
from src.services.database.categories.models import ProductType, AccountServiceType, UniversalMediaType
from src.services.database.core.database import get_db
from src.services.database.system.actions import create_ui_image, delete_ui_image
from src.services.redis.filling import filling_all_keys_category


async def update_category(
        category_id: int,
        index: int = None,
        show: bool = None,
        file_data: bytes = None,
        number_buttons_in_row: int = None,
        is_product_storage: bool = None,
        reuse_product: bool = None,
        allow_multiple_purchase: bool = None,
        price: int = None,
        cost_price: int = None,
        product_type: ProductType | None = None,
        type_account_service: AccountServiceType | None = None,
        media_type: UniversalMediaType | None = None,
) -> Categories:
    """
    :param file_data: поток байтов для создания нового ui_image, старый будет удалён
    :except IncorrectedAmountSale: Цена аккаунтов должна быть положительным числом или равно 0
    :except IncorrectedCostPrice: Себестоимость аккаунтов должна быть положительным числом
    :except IncorrectedNumberButton: Количество кнопок в строке, должно быть в диапазоне от 1 до 8
    :except AccountCategoryNotFound: Категория аккаунтов не найдена
    :except TheCategoryStorageAccount: Категория хранит аккаунты.
    :except CategoryStoresSubcategories: Категория хранит подкатегории.
    :except TheCategoryStorageProducts: При установке флага reuse_product == True, если имеются товары в категории.
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

                if product_type == ProductType.UNIVERSAL and not media_type:
                    raise ValueError(
                        "При установки хранилища универсальных товаров необходимо указать медиа тип товаров 'media_type'"
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
        if reuse_product is not None:
            if reuse_product and await get_quantity_products_in_category(category_id) > 0:
                raise TheCategoryStorageProducts()

            update_data["reuse_product"] = reuse_product
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
        if media_type is not None:
            update_data["media_type"] = media_type
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



