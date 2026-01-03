import os

from cryptography.exceptions import InvalidTag

from src.exceptions import StorageConnectionError, CryptoInitializationError, StorageNotFound
from src.services.secrets.crypto import get_crypto_context, CryptoContext, set_crypto_context
from src.services.secrets.keyring_store import load_kek
from src.services.secrets.decrypt import unwrap_dek, decrypt_text
from src.services.secrets.client import SecretsStorageClient
from src.services.secrets.runtime import get_runtime
from src.utils.core_logger import get_logger


GLOBAL_DEK_NAME = "crypto_global_dek"


def get_storage_client() -> SecretsStorageClient:
    runtime = get_runtime()
    return SecretsStorageClient(
        base_url=runtime.storage_url,
        cert=runtime.cert,
        ca=runtime.ca,
    )



def init_crypto_context():
    # для тестов и разработки
    runtime = get_runtime()
    if runtime.mode in {"DEV", "TEST"}:
        set_crypto_context(
            CryptoContext(
                kek=b"fake_kek_32byteslong____",
                dek=b"test" * 8,
                nonce_b64_dek="AAAAAAAAAAAA"  # 12 байт base64
            )
        )
        return


    # ==== PROD ====
    kek = load_kek()

    storage = get_storage_client()
    payload = storage.get_secret_string(GLOBAL_DEK_NAME)

    try:
        dek = unwrap_dek(
            encrypted_data_b64=payload["encrypted_data"],
            nonce_b64=payload["nonce"],
            kek=kek,
        )
    except InvalidTag:
        raise CryptoInitializationError("Invalid KEK or corrupted DEK")

    set_crypto_context(
        CryptoContext(kek=kek, dek=dek, nonce_b64_dek=payload["nonce"])
    )


def check_storage_service() -> bool:
    storage = get_storage_client()
    try:
        storage.health()
        return True
    except StorageConnectionError:
        return False


def get_secret(secret_name: str) -> str:

    # для тестов и разработки
    runtime = get_runtime()
    if runtime.mode in {"DEV", "TEST"}:
        value = os.getenv(secret_name)
        if value is None:
            raise RuntimeError(
                f"Secret {secret_name} not found in environment (.env)"
            )
        logger = get_logger(__name__)
        logger.debug(f"Received secret {secret_name} from ENV")
        return value


    # ==== PROD ====
    storage = get_storage_client()

    try:
        crypto = get_crypto_context()
    except RuntimeError:
        init_crypto_context()
        crypto = get_crypto_context()

    try:
        response = storage.get_secret_string(secret_name)
        logger = get_logger(__name__)
        logger.info(f"Received a secret {secret_name} from the Storage service")
    except StorageNotFound:
        raise StorageNotFound(f"Secret {secret_name} not found. Install it by running the script")

    return decrypt_text(
        encrypted_data_b64=response["encrypted_data"],
        nonce_b64=response["nonce"],
        dek=crypto.dek,
    )



