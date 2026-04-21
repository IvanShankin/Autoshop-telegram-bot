from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.database.models.categories import AccountServiceType
from src.exceptions.domain import SoldAccountNotFound, UserNotFound
from src.models.create_models.accounts import (
    CreateSoldAccountDTO,
    CreateSoldAccountTranslationDTO,
    CreateSoldAccountWithTranslationDTO,
)
from src.models.read_models import SoldAccountFull, SoldAccountSmall
from src.repository.database.categories.accounts import (
    SoldAccountsRepository,
    SoldAccountsTranslationRepository,
)
from src.repository.database.users.users import UsersRepository
from src.repository.redis import AccountsCacheRepository
from src.application.models.products.accounts.accounts_cache_filler_service import AccountsCacheFillerService


class AccountSoldService:

    def __init__(
        self,
        sold_repo: SoldAccountsRepository,
        translations_repo: SoldAccountsTranslationRepository,
        user_repo: UsersRepository,
        accounts_cache_repo: AccountsCacheRepository,
        accounts_cache_filler: AccountsCacheFillerService,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.sold_repo = sold_repo
        self.translations_repo = translations_repo
        self.user_repo = user_repo
        self.accounts_cache_repo = accounts_cache_repo
        self.accounts_cache_filler = accounts_cache_filler
        self.conf = conf
        self.session_db = session_db

    async def get_sold_accounts_by_owner_id(
        self,
        owner_id: int,
        language: str,
        *,
        get_full: bool = False,
        fallback: Optional[str] = None,
    ) -> List[SoldAccountSmall | SoldAccountFull]:
        """
        Возвращает все аккаунты, которые не удалены, отсортировано по убыванию sold_at.
        """
        if get_full:
            accounts = await self.sold_repo.get_by_owner_id_with_relations(owner_id)
            return [
                SoldAccountFull.from_orm_with_translation(acc, language=language, fallback=fallback)
                for acc in accounts
            ]

        cached = await self.accounts_cache_repo.get_sold_accounts_by_owner_id(owner_id, language)
        if cached:
            return cached

        accounts = await self.sold_repo.get_by_owner_id_with_relations(owner_id)
        result = [
            SoldAccountSmall.from_orm_with_translation(acc, language=language, fallback=fallback)
            for acc in accounts
        ]
        if result:
            await self.accounts_cache_repo.set_sold_accounts_by_owner_id(owner_id, result, language)
            await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(owner_id)
        return result

    async def get_sold_account_by_page(
        self,
        user_id: int,
        type_account_service: AccountServiceType,
        page: int,
        language: str,
        page_size: Optional[int] = None,
    ) -> List[SoldAccountSmall]:
        if page_size is None:
            page_size = self.conf.different.page_size

        accounts = await self.sold_repo.get_page_by_owner_and_service(
            user_id,
            type_account_service=type_account_service,
            page=page,
            page_size=page_size,
            active_only=True,
        )
        await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(user_id)
        return [
            SoldAccountSmall.from_orm_with_translation(acc, language=language)
            for acc in accounts
        ]

    async def get_sold_account_by_account_id(
        self,
        sold_account_id: int,
        language: str,
        *,
        fallback: Optional[str] = None,
    ) -> SoldAccountFull | None:
        cached = await self.accounts_cache_repo.get_sold_accounts_by_account_id(
            sold_account_id, language
        )
        if cached:
            return cached

        sold_account = await self.sold_repo.get_by_id_with_relations(sold_account_id)
        if not sold_account:
            return None

        await self.accounts_cache_filler.fill_sold_accounts_by_account_id(sold_account_id)
        return SoldAccountFull.from_orm_with_translation(
            sold_account,
            language=language,
            fallback=fallback,
        )

    async def get_count_sold_account(
        self,
        user_id: int,
        type_account_service: AccountServiceType,
    ) -> int:
        return await self.sold_repo.count_by_owner_id(
            user_id,
            type_account_service=type_account_service,
        )

    async def get_types_account_service_where_the_user_purchase(
        self,
        user_id: int,
    ) -> List[AccountServiceType]:
        return await self.sold_repo.get_distinct_account_service_types_by_owner(user_id)

    async def create_sold_account(
        self,
        data: CreateSoldAccountWithTranslationDTO,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> SoldAccountSmall:
        """
        :exception UserNotFound: Пользователь не найден.
        """
        user = await self.user_repo.get_by_id(data.owner_id)
        if not user:
            raise UserNotFound(f"Пользователь с ID = {data.owner_id} не найден")

        sold_payload = CreateSoldAccountDTO(
            owner_id=data.owner_id,
            account_storage_id=data.account_storage_id,
        )
        sold_account = await self.sold_repo.create_sold(**sold_payload.model_dump(exclude_unset=True))

        translation_payload = CreateSoldAccountTranslationDTO(
            sold_account_id=sold_account.sold_account_id,
            language=data.language,
            name=data.name,
            description=data.description,
        )
        await self.translations_repo.create_translate(**translation_payload.model_dump(exclude_unset=True))

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(sold_account.owner_id)
            await self.accounts_cache_filler.fill_sold_accounts_by_account_id(sold_account.sold_account_id)

        refreshed = await self.sold_repo.get_by_id_with_relations(sold_account.sold_account_id, active_only=False)
        return SoldAccountSmall.from_orm_with_translation(refreshed, language=data.language)

    async def delete_sold_account(
        self,
        sold_account_id: int,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> None:
        """
        :exception SoldAccountNotFound: Аккаунт не найден.
        """
        sold_account = await self.sold_repo.get_by_id(sold_account_id)
        if not sold_account:
            raise SoldAccountNotFound(f"Аккаунт с id = {sold_account_id} не найден")

        await self.sold_repo.delete_by_id(sold_account_id)
        await self.translations_repo.delete_all_by_sold_account_id(sold_account_id)

        if make_commit:
            await self.session_db.commit()

        if filling_redis and sold_account.owner_id is not None:
            await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(sold_account.owner_id)
            await self.accounts_cache_filler.fill_sold_accounts_by_account_id(sold_account.sold_account_id)
