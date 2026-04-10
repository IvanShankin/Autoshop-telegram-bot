from logging import Logger

from cryptography.exceptions import InvalidTag

from src.config.runtime_conf import RuntimeConfig
from src.infrastructure.crypto.key_store import KeyStore
from src.domain.crypto.key_ops import unwrap_dek
from src.domain.crypto.models import CryptoContext
from src.exceptions import CryptoInitializationError
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage

GLOBAL_DEK_NAME = "crypto_global_dek"


class CryptoProvider:
    def __init__(self):
        self._ctx: CryptoContext | None = None

    def set(self, ctx: CryptoContext):
        if self._ctx is not None:
            raise RuntimeError("CryptoContext already set")
        self._ctx = ctx

    def get(self) -> CryptoContext:
        if self._ctx is None:
            raise RuntimeError("CryptoContext not initialized")
        return self._ctx


class InitCryptoContext:
    def __init__(self, storage: SecretsStorage, keystore: KeyStore, logger: Logger, runtime_conf: RuntimeConfig):
        self.storage = storage
        self.keystore = keystore
        self.logger = logger
        self.runtime_conf = runtime_conf

    def execute(self) -> CryptoContext:
        if self.runtime_conf.env.use_secret_storage:
            ctx = CryptoContext(
                kek=b"fake_kek_32byteslong____",
                dek=b"test" * 8,
                nonce_b64_dek="AAAAAAAAAAAA"  # 12 байт base64
            )
            self.logger.info("crypto_context initialized WITHOUT storage")
            return ctx

        kek = self.keystore.load_kek()
        payload = self.storage.get_secret(GLOBAL_DEK_NAME)

        try:
            dek = unwrap_dek(
                encrypted_data_b64=payload["encrypted_data"],
                nonce_b64=payload["nonce"],
                kek=kek,
            )
        except InvalidTag:
            raise CryptoInitializationError("Invalid KEK or corrupted DEK")

        ctx = CryptoContext(kek=kek, dek=dek, nonce_b64_dek=payload["nonce"])
        self.logger.info("crypto_context initialized for PROD")

        return ctx
