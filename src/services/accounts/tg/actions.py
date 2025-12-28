import asyncio
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from opentele.api import UseCurrentSession
from opentele.td import TDesktop
from telethon.tl.types import Message, User

from src.config import TYPE_ACCOUNT_SERVICES
from src.services.database.selling_accounts.models import AccountStorage
from src.services.filesystem.account_actions import decryption_tg_account
from src.utils.core_logger import logger
from src.services.secrets import get_crypto_context

CODE_PATTERN = [
        r"\b\d{5}\b",  # например: 56741
]

async def check_valid_accounts_telethon(folder_path: str) -> User | bool:
    """
    Проверяет валидный ли аккаунт. Если аккаунт валиден, то в указанной директории будет создан файл session.session
    :param folder_path: путь к папке с данными для аккаунта. Внутри папки необходимо содержать папку tdata
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
            if me.id is not None:
                logger.info("[check_valid_accounts_telethon] - валидный аккаунт")
                return me

        logger.info("[check_valid_accounts_telethon] - НЕ валидный аккаунт")
        return False
    except:
        return False


async def check_account_validity(account_storage: AccountStorage, type_service_name: str) -> bool:
    """
    Дешифровка + проверка валидности — обёртка, возвращает True/False. Создаст временное хранилище и после удалит его
    """
    if type_service_name not in TYPE_ACCOUNT_SERVICES:
        return False

    temp_folder = None
    try:
        # decryption heavy IO в thread
        crypto = get_crypto_context()
        temp_folder = await asyncio.to_thread(decryption_tg_account, account_storage, crypto.kek)
        # проверка уже асинхронная
        is_valid = await check_valid_accounts_telethon(temp_folder)
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
        crypto = get_crypto_context()
        temp_account_path = decryption_tg_account(account_storage, crypto.kek)
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
