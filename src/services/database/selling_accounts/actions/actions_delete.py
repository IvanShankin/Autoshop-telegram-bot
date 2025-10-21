import orjson
from sqlalchemy import select, delete, distinct, update

from src.services.redis.core_redis import get_redis
from src.services.redis.filling_redis import filling_account_categories_by_service_id, \
    filling_account_categories_by_category_id, filling_product_accounts_by_category_id, \
    filling_sold_account_only_one_owner
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.models import AccountServices, AccountCategories, ProductAccounts, \
    AccountCategoryTranslation, SoldAccounts, SoldAccountsTranslation


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
            raise ValueError(f"У данного сервиса есть категории, сперва удалите их")

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

async def delete_account_category(account_category_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountCategories)
            .where(AccountCategories.account_category_id == account_category_id)
        )
        category: AccountCategories = result_db.scalar_one_or_none()
        if not category:
            raise ValueError(f"Категория с id = {account_category_id} не найдена")

        result_db = await session_db.execute(
            select(ProductAccounts)
            .where(ProductAccounts.account_category_id == account_category_id)
        )
        account = result_db.scalars().first()
        if account or category.is_accounts_storage:
            raise ValueError(f"Данная категория не должна хранить аккаунты")

        result_db = await session_db.execute(
            select(AccountCategories)
            .where(AccountCategories.parent_id == category.account_category_id)
        )
        subsidiary_category = result_db.scalars().first()
        if subsidiary_category:
            raise ValueError(f"У данной категории не должно быть подкатегорий (дочерних)")

        # удаление
        await session_db.execute(
            delete(AccountCategories)
            .where(AccountCategories.account_category_id == account_category_id)
        )
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
                await filling_sold_account_only_one_owner(account.owner_id, language=language)
                await session_redis.delete(f'sold_accounts_by_accounts_id:{account.sold_account_id}:{language}')
