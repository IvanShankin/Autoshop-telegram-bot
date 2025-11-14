import asyncio
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Tuple, List

from opentele.api import UseCurrentSession
from opentele.td import TDesktop
from telethon.tl.types import Message

from src.bot_actions.actions import send_log
from src.config import ACCOUNTS_DIR, TYPE_ACCOUNT_SERVICES
from src.services.database.selling_accounts.models import AccountStorage
from src.utils.core_logger import logger
from src.utils.secret_data import unwrap_account_key, decrypt_folder, derive_master_key


CODE_PATTERN = [
        r"\b\d{5}\b",  # например: 56741
]

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
        if not os.path.isfile(src) and not os.path.isdir(src) :
            return False
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return True
    except Exception:
        return False

async def move_file(src: str, dst: str) -> bool:
    return await asyncio.to_thread(move_file_sync, src, dst)

async def move_in_account(account: AccountStorage, type_service_name: str, status: str) -> bool:
    """
    Перенос аккаунтов к `status` удалив исходное местоположение.
    :param account: AccountStorage.
    :param type_service_name: Брать с константы TYPE_ACCOUNT_SERVICES (config.py)
    :param status: статус аккаунта который будет в конечном пути
    :return: Если возникнет ошибка или аккаунт не переместится, то вернёт False
    """
    orig = None
    final = None
    try:
        orig = str(Path(ACCOUNTS_DIR) / account.file_path)  # полный путь
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


def create_path_account(status: str, type_account_service: str, uuid: str) -> str:
    """
    Создаст путь к аккаунту.

    type_account_service брать с TYPE_ACCOUNT_SERVICES (config.py)

    :return: Полный путь. Пример: .../accounts/for_sale/telegram/gbgbfd-dnnjcs/account.enc
    """
    return str(Path(ACCOUNTS_DIR) / status / type_account_service / uuid / 'account.enc')

def _decryption_tg_account(account_storage: AccountStorage):
    """
    Расшифровывает файлы для телеграмм аккаунтов и записывает на диск расшифрованные данные во временную директорию (Temp)
    :return: путь к расшифрованным данным от аккаунта
    """
    master_key = derive_master_key()
    account_key = unwrap_account_key(account_storage.encrypted_key, master_key)

    abs_path = ACCOUNTS_DIR / Path(account_storage.file_path)
    abs_path = abs_path.resolve()
    folder_path = decrypt_folder(abs_path, account_key)
    return folder_path  # Временная папка с .session и tdata



async def _check_valid_accounts_telethon(folder_path: str) -> bool:
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


async def get_tdata_tg_acc(account_storage: AccountStorage) -> AsyncGenerator[str | bool, None]:
    """
    Расшифрует папку с тг аккаунтом и создаст архив(zip) с tdata, после второго вызова удалит все созданные временные файлы
    :return: путь к архиву
    """
    folder_path = None
    try:
        folder_path = _decryption_tg_account(account_storage)
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
    try:
        folder_path = _decryption_tg_account(account_storage)
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


async def check_account_validity(account_storage: AccountStorage, type_service_name: str) -> bool:
    """
    Дешифровка + проверка валидности — обёртка, возвращает True/False. Создаст временное хранилище и после удалит его
    """
    if type_service_name not in TYPE_ACCOUNT_SERVICES:
        return False

    temp_folder = None
    try:
        # decryption heavy IO в thread
        temp_folder = await asyncio.to_thread(_decryption_tg_account, account_storage)
        # проверка уже асинхронная
        is_valid = await _check_valid_accounts_telethon(temp_folder)
        return bool(is_valid)
    except Exception as e:
        logger.exception("Error while validating account %s: %s", getattr(account_storage, "account_storage_id", None), e)
        return False
    finally:
        if temp_folder:
            # удаление временной папки в thread, передаём kwargs
            await asyncio.to_thread(shutil.rmtree, temp_folder, ignore_errors=True)


async def get_auth_codes(account_storage: AccountStorage, limit: int = 100) -> List[Tuple[datetime, str]] | bool:
    """
    Даже если аккаунт помечен как невалидный, то всё-равно будем пытаться получить данные.
    :param account_storage: Аккаунт с которого будут браться данные.
    :param limit: Лимит сообщений которые будут извлечены
    :return: List[Tuple[время получения, код]].
    """
    result_list = []
    temp_account_path = None
    try:
        temp_account_path = _decryption_tg_account(account_storage)
        tdata_path = str(Path(temp_account_path) / 'tdata')
        tdesk = TDesktop(tdata_path)

        client = await tdesk.ToTelethon(
            session=str(Path(temp_account_path) / "session.session"),
            flag=UseCurrentSession
        )

        async with client:  # вход в аккаунт
            # Получаем N последних сообщений
            messages: List[Message] = await client.get_messages(777000, limit=limit)
            for msg in messages:
                code = None
                if msg.message:
                    for pattern in CODE_PATTERN:
                        match = re.search(pattern, msg.message)
                        if match:
                            code = match.group(0)

                if code:
                    result_list.append((msg.date, code))
    except Exception:
        # попадаем сюда если с аккаунтом проблемы
        return False
    finally:
        if temp_account_path:
            await asyncio.to_thread(shutil.rmtree, temp_account_path, ignore_errors=True)

    return result_list


