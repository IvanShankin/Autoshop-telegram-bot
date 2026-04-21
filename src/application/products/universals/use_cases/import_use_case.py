import os
import shutil
import uuid
from logging import Logger
from pathlib import Path
from typing import Dict, List

from src.application.crypto.crypto_context import CryptoProvider
from src.application.models.categories import TranslationsCategoryService
from src.application.models.products.universal import UniversalStorageService, UniversalTranslationsService, \
    UniversalProductService
from src.application.products.universals.dto import UniversalProductsParse, PreparedUniversalProduct, \
    get_import_universal_headers
from src.config import Config
from src.database.models.categories import UniversalMediaType, StorageStatus
from src.domain.crypto.encrypt import make_account_key, encrypt_file
from src.domain.crypto.key_ops import encrypt_text
from src.domain.crypto.utils import sha256_file
from src.exceptions import CategoryNotFound
from src.exceptions.business import ImportUniversalFileNotFound, ImportUniversalInvalidMediaData, InvalidFormatRows, \
    CsvHasMoreThanTwoProducts
from src.infrastructure.files.csv_parse import parse_csv_from_file
from src.infrastructure.files.file_system import extract_archive_to_temp
from src.infrastructure.files.path_builder import PathBuilder
from src.models.create_models.universal import CreateUniversalStorageWithTranslationDTO, CreateUniversalTranslationDTO, \
    CreateProductUniversalDTO
from src.models.read_models import CategoryTranslationDTO


class ImportUniversalProductUseCase:

    def __init__(
        self,
        crypto_provider: CryptoProvider,
        path_builder: PathBuilder,
        universal_storage_service: UniversalStorageService,
        universal_product_service: UniversalProductService,
        universal_translations_service: UniversalTranslationsService,
        translations_category_service: TranslationsCategoryService,
        conf: Config,
        logger: Logger,
    ):
        self.crypto_provider = crypto_provider
        self.path_builder = path_builder
        self.universal_storage_service = universal_storage_service
        self.universal_product_service = universal_product_service
        self.universal_translations_service = universal_translations_service
        self.translations_category_service = translations_category_service
        self.conf = conf
        self.logger = logger

    async def execute(
        self,
        path_to_archive: Path,
        media_type: UniversalMediaType,
        category_id: int,
        only_one: bool = False,
    ) -> int:
        """
        :param only_one: Если необходимо импортировать только один продукт
        :return: Число добавленных продуктов.
        :except ImportUniversalFileNotFound: Если указанный файл в .csv не найден.
        :except ImportUniversalInvalidMediaData: Если данные в файле .csv не совпадают с `media_type`.
        :except CategoryNotFound: Если категория не найдена.
        :except CsvHasMoreThanTwoProducts: Если имеется флаг `only_one` и продуктов для импорта более одного.
        :return int: Число добавленных продуктов.
        """
        if not os.path.isfile(path_to_archive):
            raise FileNotFoundError("Архив не найден")

        unpacked_archive = await extract_archive_to_temp(str(path_to_archive))

        manifest_file = Path(unpacked_archive) / Path("manifest.csv")
        files_dir = Path(unpacked_archive) / Path("files")

        if not os.path.isfile(manifest_file):
            raise ImportUniversalFileNotFound("manifest.csv не найден")

        if not os.path.isdir(files_dir):
            raise ImportUniversalFileNotFound("Директория для файлов не найдена")

        reader = parse_csv_from_file(manifest_file)
        rows = [
            row for row in reader
            if any(value.strip() for value in row.values() if value)
        ]

        if not get_import_universal_headers(self.conf) <= list(reader.fieldnames or []):
            raise InvalidFormatRows()

        new_products: List[UniversalProductsParse] = []
        total_added = 0

        if only_one:
            if await self.universal_product_service.get_product_universal_by_category_id(category_id):
                raise CsvHasMoreThanTwoProducts()

            if len(rows) > 1:
                raise CsvHasMoreThanTwoProducts()

        try:
            for i, row in enumerate(rows, start=1):
                descriptions = {}
                for language in self.conf.app.allowed_langs:
                    descriptions[language] = row["description_" + language]

                new_prod = UniversalProductsParse(
                    file_name=row["filename"],
                    descriptions=descriptions
                )

                self._validate_product(files_dir, new_prod, media_type)

                new_products.append(new_prod)

            total_added = await self._import_in_db(
                new_products=new_products,
                media_type=media_type,
                files_dir=files_dir,
                category_id=category_id
            )
        except Exception as e:
            shutil.rmtree(unpacked_archive, ignore_errors=True)
            shutil.rmtree(path_to_archive.parent, ignore_errors=True)
            raise e

        shutil.rmtree(unpacked_archive, ignore_errors=True)
        shutil.rmtree(path_to_archive.parent, ignore_errors=True)

        return total_added

    # =========== Helpers ===========

    def _validate_product(
        self,
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
        self,
        product: UniversalProductsParse,
        files_dir: Path,
    ) -> PreparedUniversalProduct:

        crypto = self.crypto_provider.get()
        encrypted_key_b64, dek, key_nonce = make_account_key(crypto.kek)

        storage_uuid = None
        file_path = None
        checksum = None

        if product.file_name:
            storage_uuid = str(uuid.uuid4())
            file_path = self.path_builder.build_path_universal_storage(
                StorageStatus.FOR_SALE,
                storage_uuid
            )

            encrypt_file(
                file_path=str(files_dir / product.file_name),
                encrypted_path=file_path,
                dek=dek
            )
            checksum = sha256_file(file_path)

        encrypted_descriptions = {}
        for language, text in product.descriptions.items():
            if not text:
                continue

            encrypted, nonce, _ = encrypt_text(text, dek)
            encrypted_descriptions[language] = (encrypted, nonce)

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
        self,
        prepared: PreparedUniversalProduct,
        translations_category_by_lang: Dict[str, CategoryTranslationDTO],
        media_type: UniversalMediaType,
        category_id: int,
    ):
        default_lang = self.conf.app.default_lang

        encrypted_desc, desc_nonce = prepared.encrypted_descriptions.get(default_lang, (None, None))

        storage = await self.universal_storage_service.create_universal_storage(
            data=CreateUniversalStorageWithTranslationDTO(
                name=translations_category_by_lang.get( self.conf.app.default_lang).name,
                language=default_lang,
                storage_uuid=prepared.storage_uuid,
                original_filename=prepared.original_filename,
                checksum=prepared.checksum,
                encrypted_key=prepared.encrypted_key_b64,
                encrypted_key_nonce=prepared.encrypted_key_nonce,
                media_type=media_type,
                encrypted_description=encrypted_desc,
                encrypted_description_nonce=desc_nonce,
            ),
            make_commit=True,
            filling_redis=True
        )

        for language, (desc, nonce) in prepared.encrypted_descriptions.items():
            if language == default_lang:
                continue

            translate = translations_category_by_lang.get(language)
            if not translate:
                continue

            await self.universal_translations_service.create_translation(
                data=CreateUniversalTranslationDTO(
                    universal_storage_id=storage.universal_storage_id,
                    language=language,
                    name=translate.name,
                    encrypted_description=desc,
                    encrypted_description_nonce=nonce,
                ),
                make_commit=True,
                filling_redis=True,
            )

        await self.universal_product_service.create_product_universal(
            data=CreateProductUniversalDTO(
                universal_storage_id=storage.universal_storage_id,
                category_id=category_id
            ),
            make_commit=True,
            filling_redis=True,
        )

    async def _import_in_db(
        self,
        new_products: List[UniversalProductsParse],
        media_type: UniversalMediaType,
        files_dir: Path,
        category_id: int
    ):
        total_added = 0
        crypto = self.crypto_provider.get()

        translations = await self.translations_category_service.get_all_translations_category(category_id)
        if not translations:
            raise CategoryNotFound()

        translations_category_by_lang = {}
        for translate in translations:
            translations_category_by_lang[translate.language] = translate

        for prod in new_products:
            prepared = self._prepare_product(prod, files_dir)

            await self._persist_product(
                prepared=prepared,
                translations_category_by_lang=translations_category_by_lang,
                media_type=media_type,
                category_id=category_id
            )
            total_added += 1

        return total_added
