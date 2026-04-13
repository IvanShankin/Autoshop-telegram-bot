from logging import Logger

from src.application.crypto.crypto_context import CryptoProvider
from src.database.models.categories import StorageStatus
from src.domain.crypto.decrypt import decrypt_file_to_bytes, decrypt_text
from src.domain.crypto.key_ops import unwrap_dek
from src.infrastructure.files.path_builder import PathBuilder
from src.models.read_models import ProductUniversalFull


class ValidationsUniversalProducts:

    def __init__(
        self,
        crypto_provider: CryptoProvider,
        path_builder: PathBuilder,
        logger: Logger,
    ):
        self.crypto_provider = crypto_provider
        self.path_builder = path_builder
        self.logger = logger


    async def check_valid_universal_product(
        self,
        product: ProductUniversalFull,
        status: StorageStatus,
    ) -> bool:
        """
        :param status: Статус товара в пути хранения. Будет использовать этот статус для поиска файла товара
        """
        # если есть файл проверяем, что мы можем его дешифровать
        crypto = self.crypto_provider.get()

        try:
            if product.universal_storage.original_filename:
                # Расшифровываем DEK (account_key)
                key = unwrap_dek(
                    encrypted_data_b64=product.universal_storage.encrypted_key,
                    nonce_b64=product.universal_storage.encrypted_key_nonce,
                    kek=crypto.kek
                )
                abs_path = self.path_builder.build_path_universal_storage(
                    status=status,
                    uuid=product.universal_storage.storage_uuid,
                    as_path=True
                ).resolve()

                decrypt_file_to_bytes(str(abs_path), key)  # Расшифровываем архив DEK-ом
        except Exception as e:
            self.logger.exception(f"Ошибка дешифрования файла универсального товара: {e}")
            return False

        try:
            if product.universal_storage.encrypted_tg_file_id:
                key = unwrap_dek(
                    encrypted_data_b64=product.universal_storage.encrypted_key,
                    nonce_b64=product.universal_storage.encrypted_key_nonce,
                    kek=crypto.kek
                )
                decrypt_text(
                    encrypted_data_b64=product.universal_storage.encrypted_tg_file_id,
                    nonce_b64=product.universal_storage.encrypted_tg_file_id_nonce,
                    dek=key
                )
        except Exception as e:
            self.logger.exception(f"Ошибка дешифрования данных 1 универсального товара: {e}")
            return False

        try:
            if product.universal_storage.encrypted_description:
                key = unwrap_dek(
                    encrypted_data_b64=product.universal_storage.encrypted_key,
                    nonce_b64=product.universal_storage.encrypted_key_nonce,
                    kek=crypto.kek
                )
                decrypt_text(
                    encrypted_data_b64=product.universal_storage.encrypted_description,
                    nonce_b64=product.universal_storage.encrypted_description_nonce,
                    dek=key
                )
        except Exception as e:
            self.logger.exception(f"Ошибка дешифрования данных 2 универсального товара: {e}")
            return False

        return True