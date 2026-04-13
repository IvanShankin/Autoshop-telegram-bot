import re
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import List, Tuple

from opentele.api import UseCurrentSession
from opentele.td import TDesktop
from telethon.tl.types import Message, User


CODE_PATTERN = [
        r"\b\d{5}\b",  # например: 56741
]


class TelegramAccountClient:

    def __init__(
        self,
        logger: Logger
    ):
        self.logger = logger

    async def validate(self, folder_path: str) -> User | None:
        """
        Проверяет валидный ли аккаунт. Если аккаунт валиден, то в указанной директории будет создан файл session.session
        :param folder_path: путь к папке с данными для аккаунта. Внутри папки необходимо содержать папку tdata
        :return: Вернёт пользователя, если он валидный.
        """
        try:
            tdata_path = str(Path(folder_path) / 'tdata')

            tdesk = TDesktop(tdata_path)

            client = await tdesk.ToTelethon(
                session=str(Path(folder_path) / "session.session"),
                flag=UseCurrentSession
            )

            await client.connect()

            if not await client.is_user_authorized():
                self.logger.info("[check_valid_accounts_telethon] - сессия НЕ авторизована")
                await client.disconnect()
                return

            me = await client.get_me()

            # бывают ситуации когда можно войти в аккаунт, но он не действителен (данной проверкой покрываем такие случаи)
            if me and me.id is not None:
                self.logger.info("[check_valid_accounts_telethon] - валидный аккаунт")
                return me

            self.logger.info("[check_valid_accounts_telethon] - НЕ валидный аккаунт")
            await client.disconnect()

            return
        except BaseException as e:
            self.logger.exception(f"[check_valid_accounts_telethon] error: {e}")
            return

    async def get_auth_codes(self, tdata_path: Path, limit: int) -> List[Tuple[datetime, str]] | bool:
        """
        Даже если аккаунт помечен как невалидный, то всё-равно будем пытаться получить данные.
        :param tdata_path: Путь к tdata.
        :param limit: Лимит сообщений которые будут извлечены
        :return: List[Tuple[время получения, код]].
        """
        result_list = []
        try:
            account_path = tdata_path.parent
            tdata_path = str(Path(account_path) / 'tdata')
            tdesk = TDesktop(tdata_path)

            client = await tdesk.ToTelethon(
                session=str(Path(account_path) / "session.session"),
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
        except Exception as e:
            # попадаем сюда если с аккаунтом проблемы
            self.logger.warning(f"[get_auth_codes] - Ошибка при получении кода с аккаунта: {str(e)}")
            return False

        return result_list
