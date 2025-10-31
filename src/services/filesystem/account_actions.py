import asyncio
import os
import shutil
from pathlib import Path

from opentele.api import UseCurrentSession
from opentele.td import TDesktop

from src.bot_actions.actions import send_log
from src.config import ACCOUNTS_DIR
from src.services.database.selling_accounts.models import AccountStorage, ProductAccounts
from src.utils.core_logger import logger
from src.utils.secret_data import unwrap_account_key, decrypt_folder, derive_master_key


# helper: передвигает файлы в потоке, возвращает True если всё успешно
def move_file_sync(src: str, dst: str) -> bool:
    """
        Перемещение аккаунтов

        Если путь к src не будет найден, то вернёт False
        :param src: путь к зашифрованному файл.
        :param dst: Путь к новому месту (Директория).
        :return: Bool результат
    """
    try:
        if not os.path.isfile(src):
            return False
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return True
    except Exception:
        return False

async def move_file(src: str, dst: str) -> bool:
    return await asyncio.to_thread(move_file_sync, src, dst)

async def move_in_account(account: ProductAccounts, type_service_name: str, status: str) -> bool:
    """
    Перенос аккаунтов к `status` удалив исходное местоположение.
    :param account: ProductAccounts, обязательно с подгруженным account_storage.
    :param type_service_name: Брать с константы TYPE_ACCOUNT_SERVICES (config.py)
    :param status: статус аккаунта который будет в конечном пути
    :return: Если возникнет ошибка или аккаунт не переместится, то вернёт False
    """
    orig = None
    final = None
    try:
        orig = str(Path(ACCOUNTS_DIR) / account.account_storage.file_path)  # полный путь
        final = create_path_account(
            status=status,
            type_account_service=type_service_name,
            uuid=account.account_storage.storage_uuid
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
            f"account_storage_id: {account.account_storage.account_storage_id if account.account_storage.account_storage_id else "none"} \n"
            f"Ошибка: {str(e)}"
        )
        logger.exception(f"Ошибка при переносе аккаунта к {status} %s", account.account_storage.account_storage_id)
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


def create_path_account(status: str, type_account_service: str, uuid: str) -> str:
    """
    Создаст путь к аккаунту.

    type_account_service брать с TYPE_ACCOUNT_SERVICES (config.py)

    :return: Полный путь. Пример: .../accounts/for_sale/telegram/gbgbfd-dnnjcs/account.enc
    """
    return str(Path(ACCOUNTS_DIR) / status / type_account_service / uuid / 'account.enc')

def decryption_tg_account(account_storage: AccountStorage):
    """
    Расшифровывает файлы для телеграмм аккаунтов и записывает на диск расшифрованные данные.
    :return путь к расшифрованным данным от аккаунта
    """
    master_key = derive_master_key()
    account_key = unwrap_account_key(account_storage.encrypted_key, master_key)

    abs_path = os.path.join(str(ACCOUNTS_DIR), account_storage.file_path)
    folder_path = decrypt_folder(abs_path, account_key)
    return folder_path  # Временная папка с .session и tdata



async def cheek_valid_accounts(folder_path: str) -> bool:
    """
    Проверяет валидный ли аккаунт
    :param folder_path: путь к папке с данными для аккаунта. Внутри папки необходимо содержать папку tdata и файл .session
    :return: результат проверки. True - если валидный
    """
    try:
        tdata_path = str(Path(folder_path) / 'tdata')
        tdesk = TDesktop(tdata_path)

        client = await tdesk.ToTelethon(
            session=str(Path(folder_path) / "session.session"),
            flag=UseCurrentSession
        )
        async with client:# вход в аккаунт
            me = await client.get_me()
            # бывают ситуации когда можно войти в аккаунт, но он не действителен (данной проверкой покрываем такие случаи)
            if me.id is None:
                return False

        return True
    except:
        return False

