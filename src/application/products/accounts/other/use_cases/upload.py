from logging import Logger

from src.application.crypto.crypto_context import CryptoProvider
from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.products.accounts import AccountProductService, AccountStorageService
from src.application.products.accounts.other.dto import REQUIRED_HEADERS
from src.domain.crypto.decrypt import decrypt_text
from src.domain.crypto.key_ops import unwrap_dek
from src.exceptions.business import ServerError
from src.infrastructure.files.file_system import make_csv_bytes
from src.utils.pars_number import e164_to_pretty


class UploadOtherAccountsUseCase:

    def __init__(
        self,
        crypto_provider: CryptoProvider,
        publish_event_handler: PublishEventHandler,
        account_product_service: AccountProductService,
        logger: Logger,
    ):
        self.crypto_provider = crypto_provider
        self.publish_event_handler = publish_event_handler
        self.account_product_service = account_product_service
        self.logger = logger

    async def execute(self, category_id: int) -> bytes:
        """
        :except ServerError: Любая ошибка необрабатываемая
        """
        accounts = await self.account_product_service.get_product_accounts_by_category_id(category_id, get_full=True)

        ready_acc = []
        crypto = self.crypto_provider.get()

        try:
            for acc in accounts:
                account_key = unwrap_dek(
                    acc.account_storage.encrypted_key,
                    acc.account_storage.encrypted_key_nonce,
                    crypto.kek
                )

                ready_acc.append(
                    {
                        "phone": e164_to_pretty(acc.account_storage.phone_number),
                        "login": decrypt_text(
                            acc.account_storage.login_encrypted, acc.account_storage.login_nonce, account_key
                        ),
                        "password": decrypt_text(
                            acc.account_storage.password_encrypted, acc.account_storage.password_nonce, account_key
                        ),
                    }
                )

            return make_csv_bytes(ready_acc, REQUIRED_HEADERS)
        except Exception as e:
            message = f"Ошибка при выгрузке 'других' аккаунтов {str(e)}"
            self.logger.exception(message)
            await self.publish_event_handler.send_log(text=message)

            raise ServerError() from e