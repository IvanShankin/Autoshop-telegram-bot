import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.services.redis.filling import filling_all_keys_category
from src.services.secrets.encrypt import encrypt_file
from tests.helpers.func_fabrics.category_fabric import create_category_factory
from tests.helpers.func_fabrics.other_fabric import create_new_user_fabric
from src.services.database.categories.models import UniversalMediaType, UniversalStorage, \
    UniversalStorageTranslation, ProductUniversal, SoldUniversal, StorageStatus
from src.services.database.categories.models import UniversalStoragePydantic, \
    ProductUniversalSmall, ProductUniversalFull, SoldUniversalSmall, SoldUniversalFull
from src.services.database.core.database import get_db
from src.services.redis.filling.filling_universal import filling_product_universal_by_category, \
    filling_universal_by_product_id, filling_sold_universal_by_universal_id, \
    filling_sold_universal_by_owner_id
from src.services.secrets import encrypt_text, get_crypto_context, make_account_key


async def _make_encrypted_universal_storage_file(
    dek: bytes,
    status: StorageStatus,
    uuid: str,
    file_path: str = None
) -> Path:
    from src.services.filesystem.media_paths import create_path_universal_storage
    if file_path is None:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".enc") as f:
            f.write("Данные о продукте")
            file_path = f.name
            f.close()

    encrypt_file(
        file_path=file_path,
        encrypted_path=create_path_universal_storage(status, uuid),
        dek=dek,
    )

    return Path(status.value) / Path(uuid) / Path("file.enc")


async def create_universal_storage_factory(
    media_type: UniversalMediaType = UniversalMediaType.DOCUMENT,
    original_filename: str | None = True,
    is_active: bool = True,

    language: str = "ru",
    name: str = "Universal product name",
    description: str = "Universal product description",

    encrypted_tg_file_id: str | None = "fb3425dh12hbf34bfd5dh7sjg5f",
    encrypted_tg_file_id_nonce: str | None = None,

    checksum: str = "checksum",

    key_version: int = 1,
    encryption_algo: str = "AES-GCM-256",
    status: StorageStatus = StorageStatus.FOR_SALE,
) -> tuple[UniversalStorage, UniversalStoragePydantic]:

    crypto = get_crypto_context()
    encrypted_key_b64, key, encrypted_key_nonce = make_account_key(crypto.kek)

    encrypted_description, encrypted_description_nonce, _ = encrypt_text(description, key)

    storage_uuid = str(uuid.uuid4())

    if encrypted_tg_file_id:
        encrypted_tg_file_id, encrypted_tg_file_id_nonce_new, _ = encrypt_text(encrypted_tg_file_id, key)

        if encrypted_tg_file_id_nonce is None:
            encrypted_tg_file_id_nonce = encrypted_tg_file_id_nonce_new


    if original_filename is True:
        file_path = await _make_encrypted_universal_storage_file(dek=key, status=status, uuid=storage_uuid)
        original_filename = file_path.name


    async with get_db() as session_db:

        new_storage = UniversalStorage(
            storage_uuid=storage_uuid,
            original_filename=original_filename,
            encrypted_tg_file_id=encrypted_tg_file_id,
            encrypted_tg_file_id_nonce=encrypted_tg_file_id_nonce,

            checksum=checksum,

            encrypted_key=encrypted_key_b64,
            encrypted_key_nonce=encrypted_key_nonce,
            key_version=key_version,
            encryption_algo=encryption_algo,
            status=status,

            media_type=media_type,
            is_active=is_active,
        )

        session_db.add(new_storage)
        await session_db.commit()
        await session_db.refresh(new_storage)

        new_translation = UniversalStorageTranslation(
            universal_storage_id=new_storage.universal_storage_id,
            lang=language,
            name=name,
            encrypted_description=encrypted_description,
            encrypted_description_nonce=encrypted_description_nonce,
        )

        session_db.add(new_translation)
        await session_db.commit()

        # Перечитываем объект с translations
        result = await session_db.execute(
            select(UniversalStorage)
            .options(
                selectinload(UniversalStorage.translations),
                selectinload(UniversalStorage.sold_universal),
                selectinload(UniversalStorage.product)
            )
            .where(UniversalStorage.universal_storage_id == new_storage.universal_storage_id)
        )

        new_storage: UniversalStorage = result.scalar_one()

        pydantic_model = UniversalStoragePydantic.from_orm_model(
            new_storage,
            language
        )

    return new_storage, pydantic_model


async def create_product_universal_factory(
    filling_redis: bool = True,
    universal_storage_id: int | None = None,
    encrypted_tg_file_id_nonce: str = None,
    status: StorageStatus = StorageStatus.FOR_SALE,
    category_id: int | None = None,
    language: str = "ru",
) -> tuple[ProductUniversalSmall, ProductUniversalFull]:

    async with get_db() as session_db:

        if universal_storage_id is None:
            storage, _ = await create_universal_storage_factory(
                language=language,
                encrypted_tg_file_id_nonce= encrypted_tg_file_id_nonce if encrypted_tg_file_id_nonce else None,
                status=status
            )
            universal_storage_id = storage.universal_storage_id

        if category_id is None:
            category = await create_category_factory()
            category_id = category.category_id

        new_product = ProductUniversal(
            universal_storage_id=universal_storage_id,
            category_id=category_id,
        )

        session_db.add(new_product)
        await session_db.commit()
        await session_db.refresh(new_product)

        # перечитываем с storage + translations
        result = await session_db.execute(
            select(ProductUniversal)
            .options(
                selectinload(ProductUniversal.storage)
                .selectinload(UniversalStorage.translations),
                selectinload(ProductUniversal.category),
            )
            .where(ProductUniversal.product_universal_id == new_product.product_universal_id)
        )

        new_product = result.scalar_one()

        small = ProductUniversalSmall.from_orm_model(new_product)
        full = ProductUniversalFull.from_orm_model(new_product, language)

    if filling_redis:
        await filling_product_universal_by_category()
        await filling_universal_by_product_id(full.product_universal_id)
        await filling_all_keys_category(full.category_id)

    return small, full


async def create_sold_universal_factory(
    filling_redis: bool = True,
    owner_id: int | None = None,
    universal_storage_id: int | None = None,
    is_active: bool = True,
    language: str = "ru",
) -> tuple[SoldUniversalSmall, SoldUniversalFull]:

    async with get_db() as session_db:

        if owner_id is None:
            user = await create_new_user_fabric()
            owner_id = user.user_id

        if universal_storage_id is None:
            storage, _ = await create_universal_storage_factory(language=language, is_active=is_active)
            universal_storage_id = storage.universal_storage_id

        new_sold = SoldUniversal(
            owner_id=owner_id,
            universal_storage_id=universal_storage_id,
        )

        session_db.add(new_sold)
        await session_db.commit()
        await session_db.refresh(new_sold)

        # перечитываем с storage + translations
        result = await session_db.execute(
            select(SoldUniversal)
            .options(
                selectinload(SoldUniversal.storage)
                .selectinload(UniversalStorage.translations),
            )
            .where(SoldUniversal.sold_universal_id == new_sold.sold_universal_id)
        )

        new_sold = result.scalar_one()

        small = SoldUniversalSmall.from_orm_model(new_sold, language)
        full = SoldUniversalFull.from_orm_model(new_sold, language)

    if filling_redis:
        await filling_sold_universal_by_owner_id(full.owner_id)
        await filling_sold_universal_by_universal_id(full.sold_universal_id)

    return small, full

