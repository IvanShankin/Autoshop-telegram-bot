from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.exceptions import UserNotFound, TranslationAlreadyExists
from src.exceptions.domain import UniversalStorageNotFound, CategoryNotFound
from src.services.database.categories.actions.actions_get import get_category_by_category_id
from src.services.database.categories.actions.products.universal.actions_get import get_universal_storage
from src.services.database.categories.models.product_universal import UniversalMediaType, UniversalStorage, \
    UniversalStorageTranslation, ProductUniversal, SoldUniversal, DeletedUniversal, UniversalStorageStatus
from src.services.database.categories.models.shemas.product_universal_schem import UniversalStoragePydantic
from src.services.database.core import get_db
from src.services.database.users.actions import get_user
from src.services.redis.filling import filling_all_keys_category
from src.services.redis.filling.filling_universal import filling_sold_universal_by_owner_id, \
    filling_sold_universal_by_universal_id, filling_product_universal_by_category, filling_universal_by_product_id


async def add_translate_in_universal_storage(
    universal_storage_id: int,
    language: str,
    name: str,
    encrypted_description: Optional[str]= None,
    encrypted_description_nonce: Optional[str]= None,
    filling_redis: bool = True
) -> UniversalStoragePydantic:
    """
    использовать ключ шифрования который указан в universal_storage
    :param universal_storage_id: id хранилища, где устанавливаем перевод
    :param language: язык
    :param name: имя категории
    :param encrypted_description: зашифрованное описание. Шифровать при помощи ключа который указан в universal_storage. Для каждого товара своё описание
    :param encrypted_description_nonce: nonce для зашифрованного encrypted_description
    :param filling_redis: флаг необходимости заполнить redis
    """

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(UniversalStorage)
            .options(selectinload(UniversalStorage.sold_universal), selectinload(UniversalStorage.product))
            .where(UniversalStorage.universal_storage_id == universal_storage_id)
        )
        storage: UniversalStorage = result_db.scalar_one_or_none()

        if not storage:
            raise ValueError(f"UniversalStorage с ID = {universal_storage_id} не найден")

        result_db = await session_db.execute(
            select(UniversalStorageTranslation)
            .where(
                (UniversalStorageTranslation.universal_storage_id == universal_storage_id) &
                (UniversalStorageTranslation.lang == language)
            )
        )
        translation = result_db.scalar_one_or_none()
        if translation:
            raise TranslationAlreadyExists(f"Перевод по данному языку '{language}' уже есть")

        new_translation = UniversalStorageTranslation(
            universal_storage_id=universal_storage_id,
            lang=language,
            name=name,
            encrypted_description=encrypted_description,
            encrypted_description_nonce=encrypted_description_nonce
        )
        session_db.add(new_translation)
        await session_db.commit()

        await session_db.refresh(new_translation)

        full_storage = await get_universal_storage(universal_storage_id, language)

    if filling_redis:
        for product in storage.product:
            await filling_product_universal_by_category()
            await filling_universal_by_product_id(product.product_universal_id)

        for sold in storage.sold_universal:
            await filling_sold_universal_by_owner_id(sold.owner_id)
            await filling_sold_universal_by_universal_id(sold.universal_storage_id)

    return full_storage


async def add_universal_storage(
    name: str,
    language: str,

    storage_uuid: str = None,
    file_path: str = None,
    original_filename: str = None,
    encrypted_tg_file_id: str = None,
    encrypted_tg_file_id_nonce: str = None,
    checksum: str = None,
    encrypted_key: str = None,
    encrypted_key_nonce: str = None,
    key_version: int = 1,
    encryption_algo: str = "AES-GCM-256",
    media_type: UniversalMediaType = None,
    encrypted_description: str = None,
    encrypted_description_nonce: str = None,
) -> UniversalStoragePydantic:
    """
    :param name: имя категории
    :param storage_uuid: uuid использовавшийся для создания пути
    :param file_path: путь к файлу
    :param encrypted_tg_file_id: зашифрованный file_id в телеграмме
    :param encrypted_tg_file_id_nonce: nonce для зашифрованного encrypted_tg_file_id
    :param checksum: Контроль целостности (SHA256 зашифрованного файла)
    :param encrypted_key: Персональный ключ аккаунта, зашифрованный мастер-ключом (DEK)
    :param encrypted_key_nonce: nonce, использованный при wrap (Nonce (IV) для AES-GCM (base64))
    :param key_version: Номер мастер-ключа (для ротации)
    :param encryption_algo: Алгоритм шифрования
    :param encrypted_description: зашифрованное описание
    :param encrypted_description_nonce: nonce для зашифрованного encrypted_description
    """

    if file_path and (
        original_filename is None or
        storage_uuid is None or
        checksum is None or
        encrypted_key is None or
        encrypted_key_nonce is None
    ):
        raise ValueError("Не переданы все необходимые данные для шифрования")

    if encrypted_description and (
        encrypted_description_nonce is None or
        encrypted_key is None or
        encrypted_key_nonce is None
    ):
        raise ValueError(
            "При передачи зашифрованного описания, необходимо передать: "
            "'encrypted_description_nonce', 'encrypted_key', 'encrypted_key_nonce'"
        )

    if (file_path is None) and (encrypted_description is None):
        raise ValueError("Продукт должен содержать либо файл либо описание")

    new_storage = UniversalStorage(
        storage_uuid=storage_uuid,
        file_path=file_path,
        original_filename=original_filename,
        encrypted_tg_file_id=encrypted_tg_file_id,
        encrypted_tg_file_id_nonce=encrypted_tg_file_id_nonce,
        checksum=checksum,
        encrypted_key=encrypted_key,
        encrypted_key_nonce=encrypted_key_nonce,
        key_version=key_version,
        encryption_algo=encryption_algo,
        media_type=media_type,
        status=UniversalStorageStatus.FOR_SALE
    )

    async with get_db() as session_db:
        session_db.add(new_storage)
        await session_db.commit()
        await session_db.refresh(new_storage)

    return await add_translate_in_universal_storage(
        universal_storage_id=new_storage.universal_storage_id,
        language=language,
        name=name,
        encrypted_description=encrypted_description,
        encrypted_description_nonce=encrypted_description_nonce,
    )


async def add_product_universal(
    universal_storage_id: int,
    category_id: int
):
    if not await get_universal_storage(universal_storage_id):
        raise UniversalStorageNotFound()

    if not await get_category_by_category_id(category_id):
        raise CategoryNotFound()

    new_product = ProductUniversal(
        universal_storage_id=universal_storage_id,
        category_id=category_id,
    )

    async with get_db() as session_db:
        session_db.add(new_product)
        await session_db.commit()
        await session_db.refresh(new_product)


    await filling_universal_by_product_id(new_product.product_universal_id)
    await filling_product_universal_by_category()
    await filling_all_keys_category(category_id)


async def add_sold_universal(
    owner_id: int,
    universal_storage_id: int,
):
    if not  await get_user(owner_id):
        raise UserNotFound()

    if not await get_universal_storage(universal_storage_id):
        raise UniversalStorageNotFound()


    new_sold = SoldUniversal(
        owner_id=owner_id,
        universal_storage_id=universal_storage_id,
    )

    async with get_db() as session_db:
        session_db.add(new_sold)
        await session_db.commit()
        await session_db.refresh(new_sold)

    await filling_sold_universal_by_owner_id(owner_id)
    await filling_sold_universal_by_universal_id(new_sold.sold_universal_id)


async def add_deleted_universal(universal_storage_id: int):
    async with get_db() as session_db:
        new_deleted = DeletedUniversal(
            universal_storage_id=universal_storage_id,
        )

        session_db.add(new_deleted)
        await session_db.commit()
        await session_db.refresh(new_deleted)

    return new_deleted

