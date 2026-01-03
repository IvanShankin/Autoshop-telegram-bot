import shutil
from pathlib import Path
from typing import List

import orjson
from sqlalchemy import select, delete, distinct, update

from src.config import get_config
from src.exceptions import ServiceContainsCategories, CategoryStoresSubcategories, \
    AccountCategoryNotFound, TheCategoryStorageAccount
from src.services.database.system.actions import delete_ui_image
from src.services.redis.core_redis import get_redis
from src.services.redis.filling_redis import filling_account_categories_by_service_id, \
    filling_account_categories_by_category_id, filling_product_accounts_by_category_id, \
    filling_sold_accounts_by_owner_id, filling_product_account_by_account_id
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.models import AccountServices, AccountCategories, ProductAccounts, \
    AccountCategoryTranslation, SoldAccounts, SoldAccountsTranslation, AccountStorage


async def delete_account_service(account_service_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountServices)
            .where(AccountServices.account_service_id == account_service_id)
        )
        service = result_db.scalar_one_or_none()
        if not service:
            raise ValueError(f"Сервис с id = {account_service_id} не найден")

        result_db = await session_db.execute(
            select(AccountCategories)
            .where(AccountCategories.account_service_id == account_service_id)
        )
        category = result_db.scalars().first()

        if category:
            raise ServiceContainsCategories(f"У данного сервиса есть категории, сперва удалите их")

        # удаление
        await session_db.execute(delete(AccountServices).where(AccountServices.account_service_id == account_service_id))

        # изменение последовательности индексов
        await session_db.execute(
            update(AccountServices)
            .where(AccountServices.index > service.index)
            .values(index=AccountServices.index - 1)
        )

        await session_db.commit()

        async with get_redis() as session_redis:
            result_db = await session_db.execute(select(AccountServices))
            list_service: list[AccountServices] = result_db.scalars().all()
            list_dicts = [service.to_dict() for service in list_service]

            await session_redis.set('account_services', orjson.dumps(list_dicts)) # обновляем список
            await session_redis.delete(f'account_service:{account_service_id}')

async def delete_translate_category(account_category_id: int, language: str):
    """
    :exception ValueError: Если у данной категории это единственный перевод
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountCategories)
            .where(AccountCategories.account_category_id == account_category_id)
        )
        category: AccountCategories = result_db.scalar_one_or_none()
        if not category:
            raise ValueError(f"Категория с id = {account_category_id} не найдена")

        result_db = await session_db.execute(
            select(distinct(AccountCategoryTranslation.lang))
            .where(AccountCategoryTranslation.account_category_id == account_category_id)
        )
        translations: list = result_db.scalars().all()
        if len(translations) == 1:
            raise ValueError("У категории должен быть хотя бы один перевод")

        # удаление
        await session_db.execute(
            delete(AccountCategoryTranslation)
            .where(
                (AccountCategoryTranslation.account_category_id == account_category_id) &
                (AccountCategoryTranslation.lang == language)
            )
        )

        await session_db.commit()

        # обновление redis
        await filling_account_categories_by_service_id()
        async with get_redis() as session_redis:
            await session_redis.delete(f"account_categories_by_category_id:{account_category_id}:{language}")

async def check_category_before_del(category_id: int) -> AccountCategories:
    """
    :except AccountCategoryNotFound: Категория с id = {category_id} не найдена
    :except TheCategoryStorageAccount: Данная категория не должна хранить аккаунты
    :except CategoryStoresSubcategories: У данной категории не должно быть подкатегорий (дочерних)
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountCategories)
            .where(AccountCategories.account_category_id == category_id)
        )
        category: AccountCategories = result_db.scalar_one_or_none()
        if not category:
            raise AccountCategoryNotFound(f"Категория с id = {category_id} не найдена")

        result_db = await session_db.execute(
            select(ProductAccounts)
            .where(ProductAccounts.account_category_id == category.account_category_id)
        )
        account = result_db.scalars().first()
        if account or category.is_accounts_storage:
            raise TheCategoryStorageAccount(f"Данная категория не должна хранить аккаунты")

        result_db = await session_db.execute(
            select(AccountCategories)
            .where(AccountCategories.parent_id == category.account_category_id)
        )
        subsidiary_category = result_db.scalars().first()
        if subsidiary_category:
            raise CategoryStoresSubcategories(f"У данной категории не должно быть подкатегорий (дочерних)")

        return category

async def delete_account_category(account_category_id: int):
    """Удалит категорию аккаунтов и связанную UiImage"""
    async with get_db() as session_db:
        category = await check_category_before_del(account_category_id)

        # удаление
        deleted_result = await session_db.execute(
            delete(AccountCategories)
            .where(AccountCategories.account_category_id == account_category_id)
            .returning(AccountCategories)
        )
        deleted_cat: AccountCategories = deleted_result.scalar_one_or_none()
        await session_db.execute(
            delete(AccountCategoryTranslation)
            .where(AccountCategoryTranslation.account_category_id == account_category_id)
        )

        # изменение последовательности индексов
        await session_db.execute(
            update(AccountCategories)
            .where(AccountCategories.index > category.index)
            .values(index=AccountCategories.index - 1)
        )

        await session_db.commit()

        # обновление redis
        await filling_account_categories_by_service_id()
        await filling_account_categories_by_category_id()

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
        async with get_redis() as session_redis:
            await session_redis.delete(f'product_accounts_by_account_id:{account_id}')

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
        async with get_redis() as session_redis:
            for language in all_lang:
                await filling_sold_accounts_by_owner_id(account.owner_id)
                await session_redis.delete(f'sold_accounts_by_accounts_id:{account.sold_account_id}:{language}')


async def delete_product_accounts_by_category(category_id: int):
    """Удалит аккаунты в БД и на диске(если имеется)"""
    async with get_db() as session_db:
        product_ids_result = await session_db.execute(
            select(ProductAccounts.account_id)
            .where(ProductAccounts.account_category_id == category_id)
        )
        product_ids: List[int] = product_ids_result.scalars().all()

        result_db = await session_db.execute(
            delete(AccountStorage)
            .where(
                AccountStorage.account_storage_id.in_(
                    select(ProductAccounts.account_storage_id)
                    .where(ProductAccounts.account_category_id == category_id)
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
            await filling_account_categories_by_service_id()
            await filling_account_categories_by_category_id()
            await filling_product_accounts_by_category_id()

            for acc_id in product_ids:
                await filling_product_account_by_account_id(acc_id)