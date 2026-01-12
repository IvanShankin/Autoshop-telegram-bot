import shutil
from pathlib import Path
from typing import List

from sqlalchemy import select, delete, distinct, update

from src.config import get_config
from src.exceptions import CategoryStoresSubcategories, \
    AccountCategoryNotFound, TheCategoryStorageAccount
from src.services.database.system.actions import delete_ui_image
from src.services.redis.core_redis import get_redis
from src.services.redis.filling_redis import filling_all_keys_category, filling_sold_accounts_by_owner_id, \
    filling_product_account_by_account_id, filling_product_accounts_by_category_id, filling_sold_account_by_account_id
from src.services.database.core.database import get_db
from src.services.database.product_categories.models import Categories, ProductAccounts, \
    CategoryTranslation, SoldAccounts, SoldAccountsTranslation, AccountStorage


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


async def delete_product_account(account_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(ProductAccounts)
            .where(ProductAccounts.account_id == account_id)
        )
        account: ProductAccounts = result_db.scalar_one_or_none()
        if not account:
            raise ValueError(f"Аккаунта с id = {account_id} не найдено")

        await session_db.execute(delete(ProductAccounts).where(ProductAccounts.account_id == account_id))
        await session_db.commit()

        # обновляем redis
        await filling_product_accounts_by_category_id()
        await filling_product_account_by_account_id(account_id)
        await filling_all_keys_category(account.category_id)


async def delete_sold_account(account_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(SoldAccounts)
            .where(SoldAccounts.sold_account_id == account_id)
        )
        account: SoldAccounts = result_db.scalar_one_or_none()
        if not account:
            raise ValueError(f"Аккаунта с id = {account_id} не найдено")

        result_db = await session_db.execute(
            select(SoldAccountsTranslation.lang)
            .where(SoldAccountsTranslation.sold_account_id == account_id)
            .distinct()
        )
        all_lang = result_db.scalars().all()

        await session_db.execute(delete(SoldAccounts).where(SoldAccounts.sold_account_id == account_id))
        await session_db.execute(delete(SoldAccountsTranslation).where(SoldAccountsTranslation.sold_account_id == account_id))
        await session_db.commit()

        # обновляем redis
        await filling_sold_accounts_by_owner_id(account.owner_id)
        await filling_sold_account_by_account_id(account.sold_account_id)


async def delete_product_accounts_by_category(category_id: int):
    """Удалит аккаунты в БД и на диске(если имеется)"""
    async with get_db() as session_db:
        product_ids_result = await session_db.execute(
            select(ProductAccounts.account_id)
            .where(ProductAccounts.category_id == category_id)
        )
        product_ids: List[int] = product_ids_result.scalars().all()

        result_db = await session_db.execute(
            delete(AccountStorage)
            .where(
                AccountStorage.account_storage_id.in_(
                    select(ProductAccounts.account_storage_id)
                    .where(ProductAccounts.category_id == category_id)
                )
            )
            .returning(AccountStorage)
        )
        delete_acc: List[AccountStorage] = result_db.scalars().all()
        await session_db.commit()

        for acc in delete_acc:

            if not acc.file_path: # если нет путь значит у всех остальных аккаунтов тоже нет
                continue

            folder = get_config().paths.accounts_dir / Path(acc.file_path).parent

            # удаляем каталог со всем содержимым
            shutil.rmtree(folder, ignore_errors=True)

        if delete_acc:
            await filling_all_keys_category(category_id=category_id)

            await filling_product_accounts_by_category_id()

            for acc_id in product_ids:
                await filling_product_account_by_account_id(acc_id)