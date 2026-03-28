import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.categories import AccountServiceType
from src.models.create_models.accounts import CreateAccountStorageDTO
from src.models.read_models import AccountStorageDTO
from src.models.update_models.accounts import UpdateAccountStorageDTO
from src.repository.database.categories.accounts import (
    AccountStorageRepository,
    ProductAccountsRepository,
    SoldAccountsRepository,
    TgAccountMediaRepository,
)
from src.services.models.products.accounts.accounts_cache_filler_service import AccountsCacheFillerService
from src.utils.pars_number import phone_in_e164


class AccountStorageService:

    def __init__(
        self,
        storage_repo: AccountStorageRepository,
        product_repo: ProductAccountsRepository,
        sold_repo: SoldAccountsRepository,
        tg_media_repo: TgAccountMediaRepository,
        accounts_cache_filler: AccountsCacheFillerService,
        session_db: AsyncSession,
    ):
        self.storage_repo = storage_repo
        self.product_repo = product_repo
        self.sold_repo = sold_repo
        self.tg_media_repo = tg_media_repo
        self.accounts_cache_filler = accounts_cache_filler
        self.session_db = session_db

    async def get_account_storage(self, account_storage_id: int) -> AccountStorageDTO | None:
        return await self.storage_repo.get_by_id(account_storage_id)

    async def get_all_phone_numbers_by_service(self, type_account_service: AccountServiceType) -> list[str]:
        return await self.storage_repo.get_all_phone_numbers_by_service(type_account_service)

    async def get_all_tg_ids(self) -> list[int]:
        return await self.storage_repo.get_all_tg_ids()

    def get_type_service_account(self, value: str) -> AccountServiceType | None:
        """
        :return: Если тип сервиса не найден, то вернёт None
        """
        try:
            return AccountServiceType(value)
        except ValueError:
            return None

    async def create_account_storage(
        self,
        data: CreateAccountStorageDTO,
        make_commit: Optional[bool] = True,
    ) -> AccountStorageDTO:
        """
        Путь сформируется только для аккаунтов телеграмма т.к. только их данные хранятся в файле.
        Преобразует номер телефона в необходимый формат для хранения (E164)
        :exception ValueError: `type_account_service` не найден.
        :exception ValueError: Необходимо передать login_encrypted и password_encrypted.
        """
        if not isinstance(data.type_account_service, AccountServiceType):
            raise ValueError(f"type_account_service = {data.type_account_service} не найден")

        if data.type_account_service != AccountServiceType.TELEGRAM:
            if data.login_encrypted is None or data.password_encrypted is None:
                raise ValueError("Необходимо указать login_encrypted и password_encrypted")

        values = data.model_dump(exclude_unset=True)
        values["phone_number"] = phone_in_e164(values["phone_number"])

        if data.type_account_service == AccountServiceType.TELEGRAM:
            values.setdefault("storage_uuid", str(uuid.uuid4()))

        storage = await self.storage_repo.create_storage(**values)

        if data.type_account_service == AccountServiceType.TELEGRAM:
            await self.tg_media_repo.create_media(account_storage_id=storage.account_storage_id)

        if make_commit:
            await self.session_db.commit()

        return storage

    async def update_account_storage(
        self,
        account_storage_id: int,
        data: UpdateAccountStorageDTO,
        make_commit: Optional[bool] = True,
        filling_redis: Optional[bool] = True,
    ) -> AccountStorageDTO | None:
        values = data.model_dump(exclude_unset=True)
        storage = await self.storage_repo.update(account_storage_id, **values)

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self._fill_related_accounts(account_storage_id)

        return storage

    async def _fill_related_accounts(self, account_storage_id: int) -> None:
        product_account = await self.product_repo.get_by_storage_id(account_storage_id)
        if product_account:
            await self.accounts_cache_filler.fill_product_account_by_account_id(product_account.account_id)
            await self.accounts_cache_filler.fill_product_accounts_by_category_id(product_account.category_id)

        sold_account = await self.sold_repo.get_by_storage_id(account_storage_id)
        if sold_account:
            await self.accounts_cache_filler.fill_sold_accounts_by_account_id(sold_account.sold_account_id)
            if sold_account.owner_id is not None:
                await self.accounts_cache_filler.fill_sold_accounts_by_owner_id(sold_account.owner_id)
