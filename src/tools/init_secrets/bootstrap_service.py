from src.application.crypto.crypto_context import GLOBAL_DEK_NAME
from src.domain.crypto.encrypt import wrap_dek
from src.domain.crypto.key_ops import unwrap_dek
from src.domain.crypto.models import CryptoContext
from src.domain.crypto.utils import derive_kek, gen_key
from src.exceptions import StorageNotFound
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage


class CryptoBootstrapService:
    def __init__(self, storage: SecretsStorage):
        self.storage = storage

    def init_dek(self, passphrase: str) -> CryptoContext:
        kek = derive_kek(passphrase)

        try:
            response = self.storage.get_secret(GLOBAL_DEK_NAME)
            enc_dek = response["encrypted_data"]
            nonce = response["nonce"]

            print("Global DEK already exists")

        except StorageNotFound:
            dek = gen_key()
            enc_dek, nonce, sha256 = wrap_dek(dek, kek)

            self.storage.create_secret(
                name=GLOBAL_DEK_NAME,
                encrypted_data=enc_dek,
                nonce=nonce,
                sha256=sha256,
            )

            print("Global DEK created")

        dek = unwrap_dek(enc_dek, nonce, kek)

        return CryptoContext(
            kek=kek,
            dek=dek,
            nonce_b64_dek=nonce
        )