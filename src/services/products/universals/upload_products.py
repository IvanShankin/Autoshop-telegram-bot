import os.path
import shutil
from pathlib import Path
from typing import List, AsyncGenerator

from src.exceptions import ProductNotFound
from src.services.database.categories.actions.products.universal.actions_get import \
    get_product_universal_by_category_id, get_translations_universal_storage
from src.services.database.categories.models import CategoryFull
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull
from src.services.filesystem.actions import create_temp_dir
from src.services.filesystem.universals_products import create_manifest_csv, create_import_zip
from src.services.products.universals.actions import create_path_universal_storage
from src.services.products.universals.shemas import UploadUniversalProduct, get_import_universal_headers
from src.services.secrets import get_crypto_context, unwrap_dek
from src.services.secrets.decrypt import decrypt_file, decrypt_text
from src.utils.core_logger import get_logger


async def upload_universal_products(category: CategoryFull) -> AsyncGenerator[Path, None]:
    """
    Создаст архив с товарами такой же как при импорте
    import.zip
    ├── manifest.csv
    └── files/
        ├── file_001.pdf
        ├── file_002.pdf
        ├── image_003.png
        └── ...

    Первый вызов вернёт путь к созданному архиву, второй удалит все созданные файлы
    :except ProductNotFound:
    """
    all_products: List[ProductUniversalFull] = await get_product_universal_by_category_id(
        category.category_id,
        get_full=True
    )
    if not all_products: raise ProductNotFound()

    logger = get_logger(__name__)
    crypto = get_crypto_context()

    headers = get_import_universal_headers()
    parse_products: List[UploadUniversalProduct] = []

    temp_dir = create_temp_dir()
    for_archived_dir = temp_dir / Path("uploaded_products")
    for_archived_dir.mkdir(parents=True, exist_ok=True)
    files_dir = for_archived_dir / Path("files")
    files_dir.mkdir(parents=True, exist_ok=True)

    for product in all_products:
        file_name = None
        descriptions = {}
        dek = unwrap_dek(
            encrypted_data_b64=product.universal_storage.encrypted_key,
            nonce_b64=product.universal_storage.encrypted_key_nonce,
            kek=crypto.kek
        )

        if product.universal_storage.file_path:
            path = create_path_universal_storage(
                product.universal_storage.status,
                product.universal_storage.storage_uuid,
                return_path_obj=True
            )
            if os.path.isfile(path):
                stem = Path(product.universal_storage.original_filename).stem if product.universal_storage.original_filename else "file"
                suffix = Path(product.universal_storage.original_filename).suffix if product.universal_storage.original_filename else ""

                attempt = 0
                while True:
                    postfix = f"_({attempt})" if attempt else ""
                    file_name = f"{stem}{postfix}{suffix}"
                    decrypted_path = files_dir / file_name

                    if not decrypted_path.exists():
                        break

                    attempt += 1

                decrypt_file(dek, encrypted_path=path, decrypted_path=str(decrypted_path))
            else:
                logger.warning(f"При выгрузке универсальных товаров не был найден файл по пути: {str(path)}")

        if product.universal_storage.encrypted_description:
            all_translations = await get_translations_universal_storage(product.universal_storage_id)

            for translate in all_translations:
                descriptions[translate.lang] = decrypt_text(
                    encrypted_data_b64=translate.encrypted_description,
                    nonce_b64=translate.encrypted_description_nonce,
                    dek=dek
                )

        parse_products.append(
            UploadUniversalProduct(
                file_name=file_name,
                descriptions=descriptions
            )
        )

    # сортировка по имени файла DESC
    parse_products.sort(
        key=lambda x: x.file_name or "",
    )

    # создаём manifest.csv
    manifest_path = for_archived_dir / Path("manifest.csv")
    create_manifest_csv(
        csv_path=manifest_path,
        headers=headers,
        products=parse_products
    )

    # создаём zip
    zip_path = for_archived_dir.parent / Path(f"import_category_{category.category_id}.zip")
    create_import_zip(
        base_dir=for_archived_dir,
        zip_path=zip_path
    )

    yield zip_path

    shutil.rmtree(temp_dir)

    yield None