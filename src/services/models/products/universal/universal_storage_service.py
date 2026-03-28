from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.database.models.categories import StorageStatus
from src.exceptions.business import ValueErrorService
from src.models.create_models.universal import (
    CreateUniversalStorageDTO,
    CreateUniversalStorageWithTranslationDTO,
    CreateUniversalTranslationDTO,
)
from src.models.update_models.universal import UpdateUniversalStorageDTO
from src.models.read_models import UniversalStoragePydantic
from src.repository.database.categories.universal import (
    UniversalStorageRepository,
    UniversalTranslationRepository,
)
from src.services.models.products.universal.universal_cache_filler_service import UniversalCacheFillerService


class UniversalStorageService:

    def __init__(
        self,
        storage_repo: UniversalStorageRepository,
        translation_repo: UniversalTranslationRepository,
        cache_filler: UniversalCacheFillerService,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.storage_repo = storage_repo
        self.translation_repo = translation_repo
        self.cache_filler = cache_filler
        self.conf = conf
        self.session_db = session_db

    async def get_universal_storage(
        self,
        universal_storage_id: int,
        language: str | None = None,
    ) -> UniversalStoragePydantic | None:
        if language is None:
            language = self.conf.app.default_lang

        storage = await self.storage_repo.get_orm_by_id(
            universal_storage_id,
            with_relations=True,
        )
        return UniversalStoragePydantic.from_orm_model(storage, language) if storage else None

    async def create_universal_storage(
        self,
        data: CreateUniversalStorageWithTranslationDTO,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> UniversalStoragePydantic:
        """
        :exception ValueErrorService: Если не переданы необходимые данные для шифрования.
        :exception ValueErrorService: Если не передан ни файл, ни описание.
        """
        if data.original_filename and (
            data.storage_uuid is None
            or data.checksum is None
            or data.encrypted_key is None
            or data.encrypted_key_nonce is None
        ):
            raise ValueErrorService("Не переданы все необходимые данные для шифрования")

        if data.encrypted_description and (
            data.encrypted_description_nonce is None
            or data.encrypted_key is None
            or data.encrypted_key_nonce is None
        ):
            raise ValueErrorService(
                "При передаче зашифрованного описания необходимо передать: "
                "'encrypted_description_nonce', 'encrypted_key', 'encrypted_key_nonce'"
            )

        if (data.original_filename is None) and (data.encrypted_description is None):
            raise ValueErrorService("Продукт должен содержать либо файл, либо описание")

        storage_payload = CreateUniversalStorageDTO(
            storage_uuid=data.storage_uuid,
            original_filename=data.original_filename,
            encrypted_tg_file_id=data.encrypted_tg_file_id,
            encrypted_tg_file_id_nonce=data.encrypted_tg_file_id_nonce,
            checksum=data.checksum,
            encrypted_key=data.encrypted_key,
            encrypted_key_nonce=data.encrypted_key_nonce,
            key_version=data.key_version,
            encryption_algo=data.encryption_algo,
            media_type=data.media_type,
        )
        storage = await self.storage_repo.create_storage(
            **{**storage_payload.model_dump(exclude_unset=True), "status": StorageStatus.FOR_SALE}
        )

        translation_payload = CreateUniversalTranslationDTO(
            universal_storage_id=storage.universal_storage_id,
            language=data.language,
            name=data.name,
            encrypted_description=data.encrypted_description,
            encrypted_description_nonce=data.encrypted_description_nonce,
        )
        await self.translation_repo.create_translate(**translation_payload.model_dump(exclude_unset=True))

        if make_commit:
            await self.session_db.commit()

        storage_orm = await self.storage_repo.get_orm_by_id(
            storage.universal_storage_id,
            with_relations=True,
        )

        if filling_redis:
            await self._fill_related_cache(storage_orm)

        return UniversalStoragePydantic.from_orm_model(storage_orm, data.language)

    async def update_universal_storage(
        self,
        universal_storage_id: int,
        data: UpdateUniversalStorageDTO,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> UniversalStoragePydantic | None:
        values = data.model_dump(exclude_unset=True)
        if not values:
            return await self.get_universal_storage(universal_storage_id)

        await self.storage_repo.update(universal_storage_id, **values)

        if make_commit:
            await self.session_db.commit()

        storage = await self.storage_repo.get_orm_by_id(
            universal_storage_id,
            with_relations=True,
        )

        if filling_redis:
            if storage:
                await self._fill_related_cache(storage)

        return UniversalStoragePydantic.from_orm_model(storage, self.conf.app.default_lang) if storage else None

    async def _fill_related_cache(self, storage) -> None:
        for product in storage.product:
            await self.cache_filler.fill_product_universal_by_category_id(product.category_id)
            await self.cache_filler.fill_product_universal_by_product_id(product.product_universal_id)

        for sold in storage.sold_universal:
            await self.cache_filler.fill_sold_universal_by_owner_id(sold.owner_id)
            await self.cache_filler.fill_sold_universal_by_universal_id(sold.sold_universal_id)
