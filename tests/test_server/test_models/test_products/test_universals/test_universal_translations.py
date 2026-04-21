import pytest

from src.domain.crypto.encrypt import make_account_key
from src.domain.crypto.key_ops import encrypt_text
from src.exceptions import TranslationAlreadyExists
from src.exceptions.domain import UniversalStorageNotFound
from src.models.create_models.universal import CreateUniversalTranslationDTO
from src.models.update_models.universal import UpdateUniversalTranslationDTO


def _encrypt_description(crypto_context) -> tuple[str, str]:
    _, dek, _ = make_account_key(crypto_context.kek)
    encrypted_description, encrypted_description_nonce, _ = encrypt_text("translated description", dek)
    return encrypted_description, encrypted_description_nonce


class TestUniversalTranslationsService:

    @pytest.mark.asyncio
    async def test_get_all_translations_returns_languages(self, container_fix, create_universal_storage):
        storage, _ = await create_universal_storage()
        translations = await container_fix.universal_translations_service.get_all_translations(
            storage.universal_storage_id
        )

        assert translations
        assert any(entry.language == "ru" for entry in translations)

    @pytest.mark.asyncio
    async def test_create_translation_persists(self, container_fix, create_universal_storage):
        storage, _ = await create_universal_storage()
        encrypted_description, encrypted_description_nonce = _encrypt_description(container_fix.crypto_provider.get())

        created = await container_fix.universal_translations_service.create_translation(
            CreateUniversalTranslationDTO(
                universal_storage_id=storage.universal_storage_id,
                language="en",
                name="english title",
                encrypted_description=encrypted_description,
                encrypted_description_nonce=encrypted_description_nonce,
            ),
            filling_redis=False,
        )

        translations = await container_fix.universal_translations_service.get_all_translations(
            storage.universal_storage_id
        )

        assert any(entry.language == "en" and entry.name == "english title" for entry in translations)

    @pytest.mark.asyncio
    async def test_create_translation_requires_storage(self, container_fix):
        encrypted_description, encrypted_description_nonce = _encrypt_description(container_fix.crypto_provider.get())

        with pytest.raises(UniversalStorageNotFound):
            await container_fix.universal_translations_service.create_translation(
                CreateUniversalTranslationDTO(
                    universal_storage_id=999999,
                    language="en",
                    name="english title",
                    encrypted_description=encrypted_description,
                    encrypted_description_nonce=encrypted_description_nonce,
                ),
                filling_redis=False,
            )

    @pytest.mark.asyncio
    async def test_create_translation_raises_if_language_exists(self, container_fix, create_universal_storage):
        storage, _ = await create_universal_storage()
        encrypted_description, encrypted_description_nonce = _encrypt_description(container_fix.crypto_provider.get())

        with pytest.raises(TranslationAlreadyExists):
            await container_fix.universal_translations_service.create_translation(
                CreateUniversalTranslationDTO(
                    universal_storage_id=storage.universal_storage_id,
                    language="ru",
                    name="new name",
                    encrypted_description=encrypted_description,
                    encrypted_description_nonce=encrypted_description_nonce,
                ),
                filling_redis=False,
            )

    @pytest.mark.asyncio
    async def test_update_translation_applies_changes(
        self,
        container_fix,
        create_universal_storage,
    ):
        storage, _ = await create_universal_storage()
        encrypted_description, encrypted_description_nonce = _encrypt_description(container_fix.crypto_provider.get())

        translation = await container_fix.universal_translations_service.update_translation(
            UpdateUniversalTranslationDTO(
                universal_storage_id=storage.universal_storage_id,
                language="ru",
                name="updated name",
                encrypted_description=encrypted_description,
                encrypted_description_nonce=encrypted_description_nonce,
            ),
            filling_redis=False,
        )

        assert translation is not None
        assert translation.name == "updated name"
