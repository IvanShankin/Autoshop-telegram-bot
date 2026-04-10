import os
from logging import Logger

from src.application.crypto.crypto_context import CryptoProvider
from src.config import RuntimeConfig
from src.domain.crypto.decrypt import decrypt_text
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage


class GetSecret:
    def __init__(
        self,
        storage: SecretsStorage,
        crypto_provider: CryptoProvider,
        logger: Logger,
        runtime_conf: RuntimeConfig
    ):
        self.storage = storage
        self.crypto_provider = crypto_provider
        self.logger = logger
        self.runtime_conf = runtime_conf

    def execute(self, secret_name: str) -> str:
        # если не надо
        if not self.runtime_conf.env.use_secret_storage:
            value = os.getenv(secret_name)
            if value is None:
                raise RuntimeError(
                    f"Secret {secret_name} not found in environment (.env)"
                )
            self.logger.debug(f"Received secret {secret_name} from ENV")
            return value

        crypto = self.crypto_provider.get()

        response = self.storage.get_secret(secret_name)

        return decrypt_text(
            encrypted_data_b64=response["encrypted_data"],
            nonce_b64=response["nonce"],
            dek=crypto.dek,
        )