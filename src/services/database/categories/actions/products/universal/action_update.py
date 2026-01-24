from sqlalchemy import update, select
from sqlalchemy.orm import selectinload

from src.services.database.categories.models.product_universal import UniversalMediaType, UniversalStorage, \
    UniversalStorageStatus
from src.services.database.core import get_db
from src.services.redis.filling.filling_universal import filling_product_universal_by_category, \
    filling_universal_by_product_id, filling_sold_universal_by_owner_id, filling_sold_universal_by_universal_id


async def update_universal_storage(
    universal_storage_id: int,
    storage_uuid: str = None,
    file_path: str = None,
    original_filename: str = None,
    encrypted_tg_file_id: str = None,
    encrypted_tg_file_id_nonce: str = None,
    checksum: str = None,
    encrypted_key: str = None,
    encrypted_key_nonce: str = None,
    key_version: int = None,
    encryption_algo: str = None,
    status: UniversalStorageStatus = None,
    media_type: UniversalMediaType = None,
    is_active: bool = None
) -> UniversalStorage | None:
    update_data = {}
    if not storage_uuid is None:
        update_data["storage_uuid"] = storage_uuid
    if not file_path is None:
        update_data["file_path"] = file_path
    if not original_filename is None:
        update_data["original_filename"] = original_filename
    if not encrypted_tg_file_id is None:
        update_data["encrypted_tg_file_id"] = encrypted_tg_file_id
    if not encrypted_tg_file_id_nonce is None:
        update_data["encrypted_tg_file_id_nonce"] = encrypted_tg_file_id_nonce
    if not checksum is None:
        update_data["checksum"] = checksum
    if not encrypted_key is None:
        update_data["encrypted_key"] = encrypted_key
    if not encrypted_key_nonce is None:
        update_data["encrypted_key_nonce"] = encrypted_key_nonce
    if not key_version is None:
        update_data["key_version"] = key_version
    if not encryption_algo is None:
        update_data["encryption_algo"] = encryption_algo
    if not status is None:
        update_data["status"] = status
    if not media_type is None:
        update_data["media_type"] = media_type
    if not is_active is None:
        update_data["is_active"] = is_active

    if update_data:
        async with get_db() as session_db:
            await session_db.execute(
                update(UniversalStorage)
                .where(UniversalStorage.universal_storage_id == universal_storage_id)
                .values(**update_data)
            )
            await session_db.commit()

            result = await session_db.execute(
                select(UniversalStorage)
                .options(
                    selectinload(UniversalStorage.sold_universal),
                    selectinload(UniversalStorage.product),
                    selectinload(UniversalStorage.translations),
                )
                .where(UniversalStorage.universal_storage_id == universal_storage_id)
            )

            storage = result.scalar_one_or_none()

        if storage:
            for product in storage.product:
                await filling_product_universal_by_category()
                await filling_universal_by_product_id(product.product_universal_id)

            for sold in storage.sold_universal:
                await filling_sold_universal_by_owner_id(sold.owner_id)
                await filling_sold_universal_by_universal_id(sold.sold_universal_id)

        return storage

# ДОБАВИТЬ ОБНОВЛЕНИЕ ПЕРЕВОДА ПО НЕОБХОДИМОСТИ