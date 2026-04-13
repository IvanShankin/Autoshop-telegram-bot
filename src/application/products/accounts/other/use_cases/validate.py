from logging import Logger

from src.application.crypto.crypto_context import CryptoProvider
from src.domain.crypto.decrypt import decrypt_text
from src.domain.crypto.key_ops import unwrap_dek
from src.models.read_models import AccountStorageDTO


class ValidateOtherAccountsUseCase:

    def __init__(
        self,
        crypto_provider: CryptoProvider,
        logger: Logger,
    ):
        self.crypto_provider = crypto_provider
        self.logger = logger

    async def check_valid(self, account: AccountStorageDTO) -> bool:
        try:
            crypto = self.crypto_provider.get()

            account_key = unwrap_dek(
                account.account_storage.encrypted_key,
                account.account_storage.encrypted_key_nonce,
                crypto.kek
            )

            decrypt_text(
                account.account_storage.login_encrypted, account.account_storage.login_nonce, account_key
            )
            decrypt_text(
                account.account_storage.password_encrypted, account.account_storage.password_nonce, account_key
            )
        except Exception as e:
            self.logger.exception("Ошибка при проверке other аккаунта")
            return False

        return True