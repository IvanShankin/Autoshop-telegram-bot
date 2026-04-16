import asyncio
import shutil
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import Tuple, List, TYPE_CHECKING

from src.application.crypto.crypto_context import CryptoProvider
from src.application.products.accounts.account_service import decryption_tg_account
from src.models.read_models import AccountStorageDTO


if TYPE_CHECKING:
    from src.infrastructure.telegram.account_client import TelegramAccountClient


class GetAuthCodesUseCase:

    def __init__(
        self,
        tg_client: "TelegramAccountClient",
        crypto_provider: CryptoProvider,
        logger: Logger,
    ):
        self.tg_client = tg_client
        self.crypto_provider = crypto_provider
        self.logger = logger

    async def get_auth_codes(
        self,
        account_storage: AccountStorageDTO,
        limit: int = 10
    ) -> List[Tuple[datetime, str]] | bool:
        """
        Даже если аккаунт помечен как невалидный, то всё-равно будем пытаться получить данные.
        :param account_storage: Аккаунт с которого будут браться данные.
        :param limit: Лимит сообщений которые будут извлечены
        :return: List[Tuple[время получения, код]].
        """
        temp_account_path = None
        try:
            crypto = self.crypto_provider.get()
            temp_account_path = decryption_tg_account(account_storage, crypto, account_storage.status)
            tdata_path = str(Path(temp_account_path) / 'tdata')

            return await self.tg_client.get_auth_codes(temp_account_path, limit)
        except Exception as e:
            # попадаем сюда если с аккаунтом проблемы
            self.logger.exception(
                f"[GetAuthCodesUseCase] - Ошибка при получении кода с аккаунта: "
                f"account_storage_id = {str(account_storage.account_storage_id)}"
            )
            return False
        finally:
            if temp_account_path:
                await asyncio.to_thread(shutil.rmtree, temp_account_path, ignore_errors=True)

