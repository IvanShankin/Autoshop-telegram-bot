from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import TranslationAlreadyExists
from src.exceptions.domain import SoldAccountNotFound
from src.models.create_models.accounts import CreateSoldAccountTranslationDTO
from src.models.read_models import SoldAccountSmall, SoldAccountsTranslationDTO
from src.models.update_models.accounts import UpdateSoldAccountTranslationDTO
from src.repository.database.categories.accounts import (
    SoldAccountsRepository,
    SoldAccountsTranslationRepository,
)
from src.services.models.products.accounts.accounts_cache_filler_service import AccountsCacheFillerService


class AccountTranslationsService:

    def __init__(
        self,
        sold_repo: SoldAccountsRepository,
        translations_repo: SoldAccountsTranslationRepository,
        accounts_cache_filler: AccountsCacheFillerService,
        session_db: AsyncSession,
    ):
        self.sold_repo = sold_repo
        self.translations_repo = translations_repo
        self.accounts_cache_filler = accounts_cache_filler
        self.session_db = session_db

    async def get_all_translations(self, sold_account_id: int) -> List[SoldAccountsTranslationDTO]:
        return await self.translations_repo.get_all_by_sold_account_id(sold_account_id)

    async def create_translation(
        self,
        data: CreateSoldAccountTranslationDTO,
        make_commit: Optional[bool] = True,
        filling_redis: Optional[bool] = True,
    ) -> SoldAccountSmall:
        """
        :exception SoldAccountNotFound:
        :exception TranslationAlreadyExists:
        """
        sold_account = await self.sold_repo.get_by_id_with_relations(
            data.sold_account_id,
            active_only=False,
        )
        if not sold_account:
            raise SoldAccountNotFound()

        if await self.translations_repo.exists(data.sold_account_id, data.language):
            raise TranslationAlreadyExists()

        await self.translations_repo.create_translate(**data.model_dump(exclude_unset=True))

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            if sold_account.owner_id is not None:
                await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(sold_account.owner_id)
            await self.accounts_cache_filler.fill_sold_accounts_by_account_id(data.sold_account_id)

        refreshed = await self.sold_repo.get_by_id_with_relations(
            data.sold_account_id,
            active_only=False,
        )
        return SoldAccountSmall.from_orm_with_translation(refreshed, lang=data.language)

    async def update_translation(
        self,
        data: UpdateSoldAccountTranslationDTO,
        make_commit: Optional[bool] = True,
        filling_redis: Optional[bool] = True,
    ) -> SoldAccountsTranslationDTO | None:
        values = data.model_dump(exclude_unset=True)
        translation = await self.translations_repo.update(**values)

        if make_commit:
            await self.session_db.commit()

        if translation and filling_redis:
            sold_account = await self.sold_repo.get_by_id(data.sold_account_id)
            if sold_account and sold_account.owner_id is not None:
                await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(sold_account.owner_id)
            await self.accounts_cache_filler.fill_sold_accounts_by_account_id(data.sold_account_id)

        return translation
