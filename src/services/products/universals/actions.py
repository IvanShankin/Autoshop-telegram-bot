import os
import shutil
from pathlib import Path

from src.bot_actions.messages import send_log
from src.config import Config, get_config
from src.services.database.categories.models.product_universal import UniversalStorageStatus
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull, \
    UniversalStoragePydantic
from src.services.filesystem.actions import move_file
from src.services.secrets import unwrap_dek, CryptoContext, decrypt_text, decrypt_file_to_bytes
from src.utils.core_logger import get_logger


async def check_valid_universal_product(
    product: ProductUniversalFull,
    crypto: CryptoContext,
    config: Config,
) -> bool:
    # если есть файл проверяем, что мы можем его дешифровать
    logger = get_logger(__name__)

    try:
        if product.universal_storage.file_path:
            # Расшифровываем DEK (account_key)
            key = unwrap_dek(
                encrypted_data_b64=product.universal_storage.encrypted_key,
                nonce_b64=product.universal_storage.encrypted_key_nonce,
                kek=crypto.kek
            )
            abs_path = (config.paths.universals_dir / Path(product.universal_storage.file_path)).resolve()

            decrypt_file_to_bytes(abs_path, key)  # Расшифровываем архив DEK-ом
    except Exception as e:
        logger.exception(f"Ошибка дешифрования файла универсального товара: {e}")
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
        logger.exception(f"Ошибка дешифрования данных 1 универсального товара: {e}")
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
        logger.exception(f"Ошибка дешифрования данных 2 универсального товара: {e}")
        return False

    return True


def create_path_universal_storage(status: UniversalStorageStatus, uuid: str, return_path_obj: bool = False) -> str | Path:
    """
        Создаст путь к универсальному файлу.
        :param return_path_obj: Вернёт экземпляр объекта Path
        :return: Полный путь. Пример: .../universal/for_sale/gbgbfd-dnnjcs/file.enc
    """
    path = Path(get_config().paths.universals_dir) / Path(status.value) / Path(uuid) / "file.enc"
    return path if return_path_obj else str(path)


async def move_universal_storage(storage: UniversalStoragePydantic, new_status: UniversalStorageStatus) -> Path | bool:
    """
    Перенос аккаунтов к `status` удалив исходное местоположение.
    :param status: Статус товара который будет в конечном пути
    :return: Если возникнет ошибка или аккаунт не переместится, то вернёт False
    """
    orig = None
    final = None
    try:
        orig = str(Path(get_config().paths.universals_dir) / storage.file_path)  # полный путь
        final = create_path_universal_storage(
            status=new_status,
            uuid=storage.storage_uuid,
            return_path_obj=True
        )

        moved = await move_file(orig, str(final))
        if not moved:
            return False

        # Удаление директории где хранится аккаунт (uui). Директория уже будет пустой
        if os.path.isdir(str(Path(orig).parent)):
            shutil.rmtree(str(Path(orig).parent))

        return final
    except Exception as e:
        text = (
            f"#Ошибка при переносе универсального товара к {new_status}. \n"
            f"Исходный путь: {orig if orig else "none"} \n"
            f"Финальный путь: {str(final) if str(final) else "none"} \n"
            f"account_storage_id: {storage.universal_storage_id if storage.universal_storage_id else "none"} \n"
            f"Ошибка: {str(e)}"
        )
        logger = get_logger(__name__)
        logger.exception(f"Ошибка при переносе универсального товара к {new_status} %s", storage.universal_storage_id)
        await send_log(text)
        return False

