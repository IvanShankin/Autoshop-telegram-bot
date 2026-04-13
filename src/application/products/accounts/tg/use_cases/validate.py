import asyncio
import shutil
from logging import Logger

from src.application.crypto.crypto_context import CryptoProvider
from src.database.models.categories import StorageStatus
from src.database.models.categories import AccountServiceType
from src.infrastructure.telegram.account_client import TelegramAccountClient
from src.models.read_models import AccountStorageDTO
from src.application.products.accounts.account_service import decryption_tg_account


class ValidateTgAccount:

    def __init__(
        self,
        logger: Logger,
        tg_client: TelegramAccountClient,
        crypto_provider: CryptoProvider,
    ):
        self.logger = logger
        self.tg_client = tg_client
        self.crypto_provider = crypto_provider

    async def check_account_validity(
        self,
        account_storage: AccountStorageDTO,
        type_account_service: AccountServiceType,
        status: StorageStatus
    ) -> bool:
        """
        Дешифровка + проверка валидности — обёртка, возвращает True/False. Создаст временное хранилище и после удалит его
        :param status: Используется для формирования путь к зашифрованному файлу
        """

        # если нет такого типа сервиса
        if not any(type_account_service.value == member.value for member in AccountServiceType):
            return False

        temp_folder = None
        try:
            # decryption heavy IO в thread
            crypto = self.crypto_provider.get()
            temp_folder = await asyncio.to_thread(decryption_tg_account, account_storage, crypto, status)
            # проверка уже асинхронная
            is_valid = await self.tg_client.validate(temp_folder)
            return bool(is_valid)
        except Exception as e:
            self.logger.exception("Error while validating account %s: %s",
                             getattr(account_storage, "account_storage_id", None), e)
            return False
        finally:
            if temp_folder:
                # удаление временной папки в thread, передаём kwargs
                await asyncio.to_thread(shutil.rmtree, temp_folder, ignore_errors=True)