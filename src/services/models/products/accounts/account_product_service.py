import shutil
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import TheCategoryNotStorageAccount
from src.exceptions.domain import CategoryNotFound, ProductAccountNotFound
from src.models.create_models.accounts import CreateProductAccountDTO
from src.models.read_models import ProductAccountFull, ProductAccountSmall
from src.repository.database.categories import CategoriesRepository
from src.repository.database.categories.accounts import (
    AccountStorageRepository,
    ProductAccountsRepository,
)
from src.repository.redis import AccountsCacheRepository
from src.services.filesystem.media_paths import create_path_account
from src.services.models.categories.categories_cache_filler_service import CategoriesCacheFillerService
from src.services.models.products.accounts.accounts_cache_filler_service import AccountsCacheFillerService


class AccountProductService:

    def __init__(
        self,
        product_repo: ProductAccountsRepository,
        category_repo: CategoriesRepository,
        storage_repo: AccountStorageRepository,
        accounts_cache_repo: AccountsCacheRepository,
        accounts_cache_filler: AccountsCacheFillerService,
        category_filler_service: CategoriesCacheFillerService,
        session_db: AsyncSession,
    ):
        self.product_repo = product_repo
        self.category_repo = category_repo
        self.storage_repo = storage_repo
        self.accounts_cache_repo = accounts_cache_repo
        self.accounts_cache_filler = accounts_cache_filler
        self.category_filler_service = category_filler_service
        self.session_db = session_db

    async def get_product_accounts_by_category_id(
        self,
        category_id: int,
        *,
        get_full: bool = False,
    ) -> List[ProductAccountSmall | ProductAccountFull]:
        """
        Возвращает только товары со статусом for_sale.
        """
        if get_full:
            return await self.product_repo.get_full_by_category_id(
                category_id,
                only_for_sale=True,
            )

        cached = await self.accounts_cache_repo.get_product_accounts_by_category(category_id)
        if cached:
            return cached

        product_accounts = await self.product_repo.get_by_category_id(
            category_id,
            only_for_sale=True,
        )
        if product_accounts:
            await self.accounts_cache_repo.set_product_accounts_by_category(category_id, product_accounts)

        return product_accounts

    async def get_product_account_by_account_id(self, account_id: int) -> ProductAccountFull | None:
        cached = await self.accounts_cache_repo.get_product_account_by_account_id(account_id)
        if cached:
            return cached

        product = await self.product_repo.get_full_by_account_id(account_id)
        if product:
            await self.accounts_cache_filler.fill_product_account_by_account_id(account_id)
        return product

    async def create_product_account(
        self,
        data: CreateProductAccountDTO,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> ProductAccountSmall:
        """
        :exception CategoryNotFound: Категория не найдена.
        :exception TheCategoryNotStorageAccount: Категория не является хранилищем аккаунтов.
        """
        category = await self.category_repo.get_by_id(data.category_id)
        if not category:
            raise CategoryNotFound(
                f"Категория аккаунтов с id = {data.category_id} не найдена"
            )
        if not category.is_product_storage:
            raise TheCategoryNotStorageAccount(
                f"Категория аккаунтов с id = {data.category_id} не является хранилищем аккаунтов. "
                f"Для добавления аккаунтов необходимо сделать хранилищем"
            )

        product_account = await self.product_repo.create_product(**data.model_dump(exclude_unset=True))

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.accounts_cache_filler.fill_product_account_by_account_id(product_account.account_id)
            await self.accounts_cache_filler.fill_product_accounts_by_category_id(product_account.category_id)
            await self.category_filler_service.fill_need_category(categories=[category])

        return product_account

    async def delete_product_account(
        self,
        account_id: int,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> None:
        """
        :exception ProductAccountNotFound: Аккаунт не найден.
        """
        product_account = await self.product_repo.get_by_account_id(account_id)
        if not product_account:
            raise ProductAccountNotFound(f"Аккаунт с id = {account_id} не найден")

        await self.product_repo.delete_by_account_id(account_id)

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.accounts_cache_filler.fill_product_accounts_by_category_id(product_account.category_id)
            await self.accounts_cache_filler.fill_product_account_by_account_id(account_id)
            await self.category_filler_service.fill_need_category(product_account.category_id)

    async def delete_product_accounts_by_category(
        self,
        category_id: int,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> None:
        """
        Удаляет аккаунты из БД и с диска (если есть файл).
        """
        product_ids = await self.product_repo.get_account_ids_by_category_id(category_id)
        storage_ids = await self.product_repo.get_storage_ids_by_category_id(category_id)

        deleted_storage = await self.storage_repo.delete_by_ids(storage_ids)

        if make_commit:
            await self.session_db.commit()

        for acc in deleted_storage:
            if not acc.is_file:
                continue

            folder = create_path_account(
                status=acc.status,
                type_account_service=acc.type_account_service,
                uuid=acc.storage_uuid,
                return_path_obj=True
            ).parent
            shutil.rmtree(folder, ignore_errors=True)

        if filling_redis and deleted_storage:
            await self.category_filler_service.fill_need_category(category_id)
            await self.accounts_cache_filler.fill_product_accounts_by_category_id(category_id)
            for acc_id in product_ids:
                await self.accounts_cache_filler.fill_product_account_by_account_id(acc_id)
