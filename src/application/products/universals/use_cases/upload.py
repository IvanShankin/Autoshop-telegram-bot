import csv
import os
import shutil
from logging import Logger
from pathlib import Path
from typing import List, AsyncGenerator

from src.application.crypto.crypto_context import CryptoProvider
from src.application.models.products.universal import UniversalTranslationsService, UniversalProductService
from src.application.products.universals.dto import UploadUniversalProduct, get_import_universal_headers
from src.config import Config
from src.domain.crypto.decrypt import decrypt_file, decrypt_text
from src.domain.crypto.key_ops import unwrap_dek
from src.exceptions import ProductNotFound
from src.infrastructure.files.file_system import create_temp_dir, create_import_zip
from src.infrastructure.files.path_builder import PathBuilder
from src.models.read_models import CategoryFull, ProductUniversalFull


class UploadUniversalProductsUseCase:

    def __init__(
        self,
        crypto_provider: CryptoProvider,
        path_builder: PathBuilder,
        universal_product_service: UniversalProductService,
        universal_translations_service: UniversalTranslationsService,
        conf: Config,
        logger: Logger,
    ):
        self.crypto_provider = crypto_provider
        self.path_builder = path_builder
        self.universal_product_service = universal_product_service
        self.universal_translations_service = universal_translations_service
        self.conf = conf
        self.logger = logger

    async def execute(self, category: CategoryFull) -> AsyncGenerator[Path, None]:
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
        all_products: List[ProductUniversalFull] = await self.universal_product_service.get_product_universal_by_category_id(
            category.category_id,
            get_full=True
        )
        if not all_products: raise ProductNotFound()

        crypto = self.crypto_provider.get()

        headers = get_import_universal_headers(self.conf)
        parse_products: List[UploadUniversalProduct] = []

        temp_dir = create_temp_dir(self.conf)
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

            if product.universal_storage.original_filename:
                path = self.path_builder.build_path_universal_storage(
                    product.universal_storage.status,
                    product.universal_storage.storage_uuid,
                    as_path=True
                )
                if os.path.isfile(path):
                    stem = Path(product.universal_storage.original_filename).stem
                    suffix = Path(product.universal_storage.original_filename).suffix

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
                    self.logger.warning(f"При выгрузке универсальных товаров не был найден файл по пути: {str(path)}")

            if product.universal_storage.encrypted_description:
                all_translations = await self.universal_translations_service.get_all_translations(
                    product.universal_storage_id
                )

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
        self._create_manifest_csv(
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

    def _create_manifest_csv(
        self,
        csv_path: Path,
        headers: List[str],
        products: List[UploadUniversalProduct]
    ) -> None:
        """
        Создаёт manifest.csv с товарами
        """
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=headers,
                delimiter=";",
                quoting=csv.QUOTE_MINIMAL
            )
            writer.writeheader()

            for product in products:
                row = {"filename": product.file_name or ""}

                for header in headers:
                    if header.startswith("description_"):
                        lang = header.replace("description_", "")
                        row[header] = product.descriptions.get(lang, "")

                writer.writerow(row)