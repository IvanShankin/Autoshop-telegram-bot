from typing import Iterable

from src.database.models.categories import StorageStatus, SoldAccounts
from src.models.read_models import SoldAccountSmall, SoldAccountFull
from src.repository.database.categories.accounts import (
    ProductAccountsRepository,
    SoldAccountsRepository,
)
from src.repository.redis import AccountsCacheRepository


class AccountsCacheFillerService:

    def __init__(
        self,
        product_repo: ProductAccountsRepository,
        sold_repo: SoldAccountsRepository,
        cache_repo: AccountsCacheRepository,
    ):
        self.product_repo = product_repo
        self.sold_repo = sold_repo
        self.cache_repo = cache_repo

    async def fill_product_accounts_by_category_id(self, category_id: int) -> None:
        product_accounts = await self.product_repo.get_by_category_id(
            category_id, only_for_sale=True
        )

        if not product_accounts:
            await self.cache_repo.delete_product_accounts_by_category(category_id)
            return

        await self.cache_repo.set_product_accounts_by_category(category_id, product_accounts)

    async def fill_product_account_by_account_id(self, account_id: int) -> None:
        product_account = await self.product_repo.get_full_by_account_id(account_id)
        if not product_account:
            await self.cache_repo.delete_product_account_by_account_id(account_id)
            return

        if product_account.account_storage.status != StorageStatus.FOR_SALE:
            await self.cache_repo.delete_product_account_by_account_id(account_id)
            return

        await self.cache_repo.set_product_account_by_account_id(product_account)

    async def fill_sold_accounts_by_owner_id(self, owner_id: int) -> None:
        sold_accounts = await self.sold_repo.get_by_owner_id_with_relations(
            owner_id,
            active_only=True,
            order_desc=True,
        )

        if not sold_accounts:
            await self.cache_repo.delete_sold_accounts_by_owner_id(owner_id)
            return

        languages = self._extract_languages(sold_accounts)
        if not languages:
            await self.cache_repo.delete_sold_accounts_by_owner_id(owner_id)
            return

        for language in languages:
            items = [
                SoldAccountSmall.from_orm_with_translation(account, language=language)
                for account in sold_accounts
            ]
            await self.cache_repo.set_sold_accounts_by_owner_id(owner_id, items, language)

    async def fill_sold_accounts_by_account_id(self, sold_account_id: int) -> None:
        sold_account = await self.sold_repo.get_by_id_with_relations(
            sold_account_id,
            active_only=True,
        )
        if not sold_account:
            await self.cache_repo.delete_sold_accounts_by_account_id(sold_account_id)
            return

        languages = self._extract_languages([sold_account])
        if not languages:
            await self.cache_repo.delete_sold_accounts_by_account_id(sold_account_id)
            return

        for language in languages:
            dto = SoldAccountFull.from_orm_with_translation(sold_account, language=language)
            await self.cache_repo.set_sold_accounts_by_account_id(dto, language)

    @staticmethod
    def _extract_languages(accounts: Iterable[SoldAccounts]) -> set[str]:
        return {
            translate.language
            for account in accounts
            for translate in account.translations
            if translate.language
        }
