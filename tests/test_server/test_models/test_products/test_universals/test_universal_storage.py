import uuid

import pytest

from src.application._secrets.crypto_context import get_crypto_context
from src.database.models.categories import StorageStatus, UniversalMediaType
from src.domain.crypto.encrypt import make_account_key
from src.domain.crypto.key_ops import encrypt_text
from src.exceptions.business import ValueErrorService
from src.models.create_models.universal import CreateUniversalStorageWithTranslationDTO
from src.models.update_models.universal import UpdateUniversalStorageDTO


def _build_storage_encryption_payload() -> tuple[str, bytes, str, str, str]:
    encrypted_key, key, encrypted_key_nonce = make_account_key(get_crypto_context().kek)
    encrypted_description, encrypted_description_nonce, _ = encrypt_text("description", key)
    return encrypted_key, key, encrypted_key_nonce, encrypted_description, encrypted_description_nonce


class TestUniversalStorageService:

    @pytest.mark.asyncio
    async def test_get_universal_storage_returns_storage(self, container_fix, create_universal_storage):
        storage, pydantic = await create_universal_storage()
        result = await container_fix.universal_storage_service.get_universal_storage(
            storage.universal_storage_id,
            language="ru",
        )

        assert result is not None
        assert result.universal_storage_id == storage.universal_storage_id
        assert result.name == pydantic.name

    @pytest.mark.asyncio
    async def test_create_universal_storage_requires_encryption_fields(self, container_fix):
        dto = CreateUniversalStorageWithTranslationDTO(
            language="ru",
            name="test",
            original_filename="file.enc",
        )

        with pytest.raises(ValueErrorService):
            await container_fix.universal_storage_service.create_universal_storage(
                dto,
                filling_redis=False,
            )

    @pytest.mark.asyncio
    async def test_create_universal_storage_persists_and_returns(self, container_fix):
        encrypted_key, key, encrypted_key_nonce, encrypted_description, encrypted_description_nonce = (
            _build_storage_encryption_payload()
        )
        dto = CreateUniversalStorageWithTranslationDTO(
            language="en",
            name="created universal",
            encrypted_description=encrypted_description,
            encrypted_description_nonce=encrypted_description_nonce,
            storage_uuid=str(uuid.uuid4()),
            checksum="checksum",
            encrypted_key=encrypted_key,
            encrypted_key_nonce=encrypted_key_nonce,
            media_type=UniversalMediaType.DOCUMENT,
        )

        created = await container_fix.universal_storage_service.create_universal_storage(
            dto,
            filling_redis=False,
        )

        assert created.universal_storage_id is not None
        assert created.name == "created universal"
        assert created.status == StorageStatus.FOR_SALE

    @pytest.mark.asyncio
    async def test_update_universal_storage_applies_changes(self, container_fix, create_universal_storage):
        storage, _ = await create_universal_storage()

        updated = await container_fix.universal_storage_service.update_universal_storage(
            storage.universal_storage_id,
            UpdateUniversalStorageDTO(status=StorageStatus.BOUGHT),
            filling_redis=False,
        )

        assert updated is not None
        assert updated.status == StorageStatus.BOUGHT
