from sqlalchemy import select, delete, distinct, update

from src.exceptions import CategoryStoresSubcategories, \
    AccountCategoryNotFound, TheCategoryStorageAccount
from src.services.database.categories.models import Categories, ProductAccounts, \
    CategoryTranslation
from src.services.database.core.database import get_db
from src.services.database.system.actions import delete_ui_image
from src.services.redis.filling import filling_all_keys_category


async def delete_translate_category(category_id: int, language: str):
    """
    :exception ValueError: Если у данной категории это единственный перевод
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Categories)
            .where(Categories.category_id == category_id)
        )
        category: Categories = result_db.scalar_one_or_none()
        if not category:
            raise ValueError(f"Категория с id = {category_id} не найдена")

        result_db = await session_db.execute(
            select(distinct(CategoryTranslation.lang))
            .where(CategoryTranslation.category_id == category_id)
        )
        translations: list = result_db.scalars().all()
        if len(translations) == 1:
            raise ValueError("У категории должен быть хотя бы один перевод")

        # удаление
        await session_db.execute(
            delete(CategoryTranslation)
            .where(
                (CategoryTranslation.category_id == category_id) &
                (CategoryTranslation.lang == language)
            )
        )

        await session_db.commit()

        # обновление redis
        await filling_all_keys_category(category_id=category_id)


async def check_category_before_del(category_id: int) -> Categories:
    """
    :except AccountCategoryNotFound: Категория с id = {category_id} не найдена
    :except TheCategoryStorageAccount: Данная категория не должна хранить аккаунты
    :except CategoryStoresSubcategories: У данной категории не должно быть подкатегорий (дочерних)
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Categories)
            .where(Categories.category_id == category_id)
        )
        category: Categories = result_db.scalar_one_or_none()
        if not category:
            raise AccountCategoryNotFound(f"Категория с id = {category_id} не найдена")

        result_db = await session_db.execute(
            select(ProductAccounts)
            .where(ProductAccounts.category_id == category.category_id)
        )
        account = result_db.scalars().first()
        if account or category.is_product_storage:
            raise TheCategoryStorageAccount(f"Данная категория не должна хранить аккаунты")

        result_db = await session_db.execute(
            select(Categories)
            .where(Categories.parent_id == category.category_id)
        )
        subsidiary_category = result_db.scalars().first()
        if subsidiary_category:
            raise CategoryStoresSubcategories(f"У данной категории не должно быть подкатегорий (дочерних)")

        return category


async def delete_category(category_id: int):
    """Удалит категорию аккаунтов и связанную UiImage"""
    async with get_db() as session_db:
        category = await check_category_before_del(category_id)

        # удаление
        deleted_result = await session_db.execute(
            delete(Categories)
            .where(Categories.category_id == category_id)
            .returning(Categories)
        )
        deleted_cat: Categories = deleted_result.scalar_one_or_none()
        await session_db.execute(
            delete(CategoryTranslation)
            .where(CategoryTranslation.category_id == category_id)
        )

        # изменение последовательности индексов
        await session_db.execute(
            update(Categories)
            .where(Categories.index > category.index)
            .values(index=Categories.index - 1)
        )

        await session_db.commit()

        # обновление redis
        await filling_all_keys_category()

    if deleted_cat and deleted_cat.ui_image_key:
        await delete_ui_image(deleted_cat.ui_image_key)

