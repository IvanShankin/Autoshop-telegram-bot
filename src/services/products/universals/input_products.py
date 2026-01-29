import os.path
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Tuple

from src.config import get_config
from src.exceptions import InvalidFormatRows, CategoryNotFound
from src.exceptions.business import ImportUniversalFileNotFound, ImportUniversalInvalidMediaData
from src.services.database.categories.actions import get_category_by_category_id, get_all_translations_category
from src.services.database.categories.actions.products.universal.actions_add import add_universal_storage, \
    add_translate_in_universal_storage, add_product_universal
from src.services.database.categories.models import CategoryTranslation
from src.services.database.categories.models.product_universal import UniversalMediaType, UniversalStorageStatus
from src.services.filesystem.actions import extract_archive_to_temp
from src.services.filesystem.csv_parse import parse_csv_from_file
from src.services.products.universals.actions import create_path_universal_storage
from src.services.products.universals.shemas import UniversalProductsParse, \
    get_import_universal_headers, PreparedUniversalProduct
from src.services.secrets import encrypt_text, make_account_key, get_crypto_context, sha256_file, CryptoContext
from src.services.secrets.encrypt import encrypt_file


def _validate_product(
    files_dir: Path,
    product: UniversalProductsParse,
    media_type: UniversalMediaType,
):
    has_file = bool(product.file_name)
    has_description = any(v.strip() for v in product.descriptions.values())

    if product.file_name and not os.path.isfile(files_dir / Path(product.file_name)):
        raise ImportUniversalFileNotFound(product.file_name)

    if media_type == UniversalMediaType.DESCRIPTION and not has_description:
        raise ImportUniversalInvalidMediaData()

    if media_type in {
        UniversalMediaType.DOCUMENT,
        UniversalMediaType.IMAGE,
        UniversalMediaType.VIDEO
    } and not has_file:
        raise ImportUniversalInvalidMediaData()

    if media_type == UniversalMediaType.MIXED and not (has_file and has_description):
        raise ImportUniversalInvalidMediaData()


def _prepare_product(
    product: UniversalProductsParse,
    files_dir: Path,
    crypto: CryptoContext,
) -> PreparedUniversalProduct:

    encrypted_key_b64, dek, key_nonce = make_account_key(crypto.kek)

    storage_uuid = None
    file_path = None
    checksum = None

    if product.file_name:
        storage_uuid = str(uuid.uuid4())
        file_path = create_path_universal_storage(
            UniversalStorageStatus.FOR_SALE,
            storage_uuid
        )

        encrypt_file(
            file_path=str(files_dir / product.file_name),
            encrypted_path=file_path,
            dek=dek
        )
        checksum = sha256_file(file_path)

    encrypted_descriptions = {}
    for lang, text in product.descriptions.items():
        if not text:
            continue

        encrypted, nonce, _ = encrypt_text(text, dek)
        encrypted_descriptions[lang] = (encrypted, nonce)

    return PreparedUniversalProduct(
        storage_uuid=storage_uuid,
        file_path=file_path,
        original_filename=product.file_name,
        checksum=checksum,
        encrypted_key_b64=encrypted_key_b64,
        encrypted_key_nonce=key_nonce,
        encrypted_descriptions=encrypted_descriptions,
    )


async def _persist_product(
    prepared: PreparedUniversalProduct,
    translations_category_by_lang: Dict[str, CategoryTranslation],
    media_type: UniversalMediaType,
    category_id: int,
):
    conf = get_config()
    default_lang = conf.app.default_lang

    encrypted_desc, desc_nonce = prepared.encrypted_descriptions.get(default_lang, (None, None))

    storage = await add_universal_storage(
        name=translations_category_by_lang.get(conf.app.default_lang).name,
        language=default_lang,
        storage_uuid=prepared.storage_uuid,
        file_path=prepared.file_path,
        original_filename=prepared.file_path,
        checksum=prepared.checksum,
        encrypted_key=prepared.encrypted_key_b64,
        encrypted_key_nonce=prepared.encrypted_key_nonce,
        media_type=media_type,
        encrypted_description=encrypted_desc,
        encrypted_description_nonce=desc_nonce,
    )

    for lang, (desc, nonce) in prepared.encrypted_descriptions.items():
        if lang == default_lang:
            continue

        translate = translations_category_by_lang.get(lang)
        if not translate:
            continue

        await add_translate_in_universal_storage(
            universal_storage_id=storage.universal_storage_id,
            language=lang,
            name=translate.name,
            encrypted_description=desc,
            encrypted_description_nonce=nonce,
        )

    await add_product_universal(
        universal_storage_id=storage.universal_storage_id,
        category_id=category_id
    )


async def _import_in_db(
    new_products: List[UniversalProductsParse],
    media_type: UniversalMediaType,
    files_dir: Path,
    category_id: int
):
    total_added = 0
    crypto = get_crypto_context()

    translations = await get_all_translations_category(category_id)
    if not translations:
        raise CategoryNotFound()

    translations_category_by_lang = {}
    for translate in translations:
        translations_category_by_lang[translate.lang] = translate


    for prod in new_products:
        prepared = _prepare_product(prod, files_dir, crypto)

        await _persist_product(
            prepared=prepared,
            translations_category_by_lang=translations_category_by_lang,
            media_type=media_type,
            category_id=category_id
        )
        total_added += 1

    return total_added


async def input_universal_products(
    path_to_archive: str,
    media_type: UniversalMediaType,
    category_id: int,
) -> int:
    """
    :param path_to_archive:
    :param media_type:
    :param category_id:
    :return:
    :except ImportUniversalFileNotFound: Если указанный файл в .csv не найден.
    :except ImportUniversalInvalidMediaData: Если данные в файле .csv не совпадают с `media_type`.
    :except CategoryNotFound: Если категория не найдена.
    :return int: Число добавленных продуктов.
    """
    if not os.path.isfile(path_to_archive):
        raise FileNotFoundError("Архив не найден")

    unpacked_archive = await extract_archive_to_temp(path_to_archive)

    manifest_file = Path(unpacked_archive) / Path("manifest.csv")
    files_dir = Path(unpacked_archive) / Path("files")

    if not os.path.isfile(manifest_file):
        raise FileNotFoundError("manifest.csv не найден")

    if not os.path.isdir(files_dir):
        raise NotADirectoryError("Директория для файлов не найдена")

    reader = parse_csv_from_file(manifest_file)
    conf = get_config()

    if not get_import_universal_headers() <= list(reader.fieldnames or []):
        raise InvalidFormatRows()

    new_products: List[UniversalProductsParse] = []
    total_added = 0

    try:
        for i, row in enumerate(reader, start=1):
            descriptions = {}
            for lang in conf.app.allowed_langs:
                descriptions[lang] = row["description_" + lang]

            new_prod = UniversalProductsParse(
                file_name=row["filename"],
                descriptions=descriptions
            )

            _validate_product(files_dir, new_prod, media_type)

            new_products.append(new_prod)

        total_added = await _import_in_db(
            new_products=new_products,
            media_type=media_type,
            files_dir=files_dir,
            category_id=category_id
        )
    except Exception as e:
        shutil.rmtree(unpacked_archive, ignore_errors=True)
        raise e

    shutil.rmtree(unpacked_archive, ignore_errors=True)

    return total_added

