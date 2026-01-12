import asyncio
import os
import shutil
from pathlib import Path
from typing import AsyncGenerator

from src.bot_actions.messages import send_log
from src.config import get_config
from src.services.database.categories.models import AccountStorage, AccountStoragePydantic
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.filesystem.actions import move_file
from src.utils.core_logger import get_logger
from src.services.secrets import decrypt_folder, get_crypto_context, unwrap_dek, CryptoContext


async def move_in_account(account: AccountStorage, type_service_name: AccountServiceType, status: str) -> bool:
    """
    Перенос аккаунтов к `status` удалив исходное местоположение.
    :param account: AccountStorage.
    :param type_service_name: тип сервиса аккаунта
    :param status: статус аккаунта который будет в конечном пути
    :return: Если возникнет ошибка или аккаунт не переместится, то вернёт False
    """
    orig = None
    final = None
    try:
        orig = str(Path(get_config().paths.accounts_dir) / account.file_path)  # полный путь
        final = create_path_account(
            status=status,
            type_account_service=type_service_name,
            uuid=account.storage_uuid
        )

        moved = await move_file(orig, final)
        if not moved:
            return False

        # Удаление директории где хранится аккаунт (uui). Директория уже будет пустой
        if os.path.isdir(str(Path(orig).parent)):
            shutil.rmtree(str(Path(orig).parent))

        return True
    except Exception as e:
        text = (
            f"#Ошибка при переносе аккаунта к {status}. \n"
            f"Исходный путь: {orig if orig else "none"} \n"
            f"Финальный путь: {final if final else "none"} \n"
            f"account_storage_id: {account.account_storage_id if account.account_storage_id else "none"} \n"
            f"Ошибка: {str(e)}"
        )
        logger = get_logger(__name__)
        logger.exception(f"Ошибка при переносе аккаунта к {status} %s", account.account_storage_id)
        await send_log(text)
        return False


# helper: rename temp -> final (atomic)
def rename_sync(src: str, dst: str) -> bool:
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(src, dst)  # atomic on same filesystem
        return True
    except Exception:
        return False


async def rename_file(src: str, dst: str) -> bool:
    return await asyncio.to_thread(rename_sync, src, dst)


def create_path_account(status: str, type_account_service: AccountServiceType, uuid: str) -> str:
    """
    Создаст путь к аккаунту.

    type_account_service брать с get_config().app.type_account_services (config)

    :return: Полный путь. Пример: .../accounts/for_sale/telegram/gbgbfd-dnnjcs/account.enc
    """
    return str(Path(get_config().paths.accounts_dir) / status / type_account_service.value / uuid / 'account.enc')


def decryption_tg_account(
    account_storage: AccountStorage | AccountStoragePydantic,
    crypto: CryptoContext,
):
    """
    Расшифровывает файлы Telegram-аккаунта во временную директорию.
    :param kek: (Key Encryption Key) передаётся из runtime.
    """

    # Расшифровываем DEK (account_key)
    account_key = unwrap_dek(
        encrypted_data_b64=account_storage.encrypted_key,
        nonce_b64=account_storage.encrypted_key_nonce,
        kek=crypto.kek
    )

    abs_path = (get_config().paths.accounts_dir / Path(account_storage.file_path)).resolve()

    folder_path = decrypt_folder(abs_path, account_key) # Расшифровываем архив DEK-ом

    return folder_path


async def get_tdata_tg_acc(account_storage: AccountStorage) -> AsyncGenerator[str | bool, None]:
    """
    Расшифрует папку с тг аккаунтом и создаст архив(zip) с tdata, после второго вызова удалит все созданные временные файлы
    :return: путь к архиву
    """
    folder_path = None
    try:
        crypto = get_crypto_context()
        folder_path = decryption_tg_account(account_storage, crypto)
        dir_for_tdata = Path(folder_path) / f'{account_storage.account_storage_id}_tdata'
        dir_for_tdata.mkdir(exist_ok=True)
        result = await move_file(str(Path(folder_path) / 'tdata'), str(dir_for_tdata))

        if not result:
            yield False
        else:

            archive_path = shutil.make_archive(
                base_name=str(Path(folder_path) / f'{account_storage.account_storage_id}_tdata'),
                format="zip",
                root_dir=str(dir_for_tdata) # должна быть директория с tdata
            )
            yield archive_path
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception("#Ошибка при получении tdata с аккаунта %s: %s", getattr(account_storage, "account_storage_id", None), e)
        yield False
    finally:
        if folder_path:
            await asyncio.to_thread(shutil.rmtree, folder_path, ignore_errors=True)


async def get_session_tg_acc(account_storage: AccountStorage) -> AsyncGenerator[str | bool, None]:
    """
    Расшифрует папку с тг аккаунтом и вернёт путь к файлу .session, после второго вызова удалит все созданные временные файлы
    :return: Путь к файлу
    """
    folder_path = None
    logger = get_logger(__name__)

    try:
        crypto = get_crypto_context()
        folder_path = decryption_tg_account(account_storage, crypto)
        session_path = str(Path(folder_path) / 'session.session')
        if os.path.isfile(session_path):
            yield session_path
        else:
            logger.warning(
                "Не_найден_файл при получении session с аккаунта %s: %s",
                getattr(account_storage, "account_storage_id", None),
                f"Путь поиска: {session_path}"
            )
            yield False
    except Exception as e:
        logger.exception("#Ошибка при получении session с аккаунта %s: %s", getattr(account_storage, "account_storage_id", None), e)
        yield False
    finally:
        if folder_path:
            await asyncio.to_thread(shutil.rmtree, folder_path, ignore_errors=True)


