from typing import List, Optional

from src.models.read_models import ProductAccountSmall, ProductAccountFull, SoldAccountSmall, SoldAccountFull
from src.repository.redis.base import BaseRedisRepo


class AccountsCacheRepository(BaseRedisRepo):

    def _key_product_account_by_category(self, category_id: int) -> str:
        return f"product_accounts_by_category:{category_id}"

    def _key_product_account_by_account_id(self, account_id: int) -> str:
        return f"product_account:{account_id}"

    def _key_sold_accounts_by_owner_id(self, owner_id: int, language: str) -> str:
        return f"sold_accounts_by_owner_id:{owner_id}:{language}"

    def _key_pattern_by_owner(self, owner_id: int) -> str:
        return f"sold_accounts_by_owner_id:{owner_id}:*"

    def _key_sold_accounts_by_account_id(self, account_id: int, language: str) -> str:
        return f"sold_account:{account_id}:{language}"

    def _key_pattern_by_account(self, account_id: int) -> str:
        return f"sold_account:{account_id}:*"

    # ==== product_accounts_by_category ====

    async def set_product_accounts_by_category(self, category_id: int, product_accounts: List[ProductAccountSmall]) -> None:
        await self._set_many(
            self._key_product_account_by_category(category_id),
            product_accounts
        )

    async def get_product_accounts_by_category(self, category_id: int) -> List[ProductAccountSmall]:
        return await self._get_many(
            self._key_product_account_by_category(category_id),
            ProductAccountSmall
        )

    async def delete_product_accounts_by_category(self, category_id: int) -> None:
        await self.redis_session.delete(self._key_product_account_by_category(category_id))

    # ==== product_account_by_account_id ====

    async def set_product_account_by_account_id(self, product_account: ProductAccountFull) -> None:
        return await self._set_one(
            self._key_product_account_by_account_id(product_account.account_id),
            product_account
        )

    async def get_product_account_by_account_id(self, account_id: int) -> Optional[ProductAccountFull]:
        return await self._get_one(
            self._key_product_account_by_account_id(account_id),
            ProductAccountFull
        )

    async def delete_product_account_by_account_id(self, account_id: int) -> None:
        await self.redis_session.delete(self._key_product_account_by_account_id(account_id))

    # ==== sold_accounts_by_owner_id ====

    async def set_sold_accounts_by_owner_id(
        self,
        owner_id: int,
        sold_accounts: List[SoldAccountSmall],
        language: str
    ) -> None:
        await self._set_many(
            self._key_sold_accounts_by_owner_id(owner_id, language),
            sold_accounts,
            ttl=int(self.conf.redis_time_storage.sold_accounts_by_owner.total_seconds()),
        )

    async def get_sold_accounts_by_owner_id(self, owner_id: int, language: str) -> List[SoldAccountSmall]:
        return await self._get_many(
            self._key_sold_accounts_by_owner_id(owner_id, language),
            SoldAccountSmall
        )

    async def delete_sold_accounts_by_owner_id(self, owner_id: int, ) -> None:
        await self.delete_keys_by_pattern(self._key_pattern_by_owner(owner_id))

    # ==== sold_accounts_by_account_id ====

    async def set_sold_accounts_by_account_id(self, sold_account: SoldAccountFull, language: str) -> None:
        return await self._set_one(
            self._key_sold_accounts_by_account_id(sold_account.sold_account_id, language),
            sold_account
        )

    async def get_sold_accounts_by_account_id(self, account_id: int, language: str) -> Optional[SoldAccountFull]:
        return await self._get_one(
            self._key_sold_accounts_by_account_id(account_id, language),
            SoldAccountFull
        )

    async def delete_sold_accounts_by_account_id(self, account_id: int, ) -> None:
        await self.delete_keys_by_pattern(self._key_pattern_by_account(account_id))