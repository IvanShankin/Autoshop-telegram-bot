import os

from cryptography.exceptions import InvalidTag
from dotenv import load_dotenv

from src.config.paths_conf import SSL_CLIENT_CERT_FILE, SSL_CLIENT_KEY_FILE, SSL_CA_FILE
from src.exceptions.service_exceptions import StorageConnectionError, CryptoInitializationError, \
    StorageNotFound

from src.services.secrets.crypto import get_crypto_context, CryptoContext, set_crypto_context
from src.services.secrets.utils import derive_kek, gen_key, read_secret
from src.services.secrets.encrypt import wrap_dek, encrypt_text
from src.services.secrets.decrypt import unwrap_dek, decrypt_text
from src.services.secrets.client import SecretsStorageClient

load_dotenv()


STORAGE_SERVER_URL = os.getenv("STORAGE_SERVER_URL")
CERT = (
    str(SSL_CLIENT_CERT_FILE),
    str(SSL_CLIENT_KEY_FILE)
)
CA = str(SSL_CA_FILE)
GLOBAL_DEK_NAME = "crypto_global_dek"



def get_storage_client() -> SecretsStorageClient:
    return SecretsStorageClient(
        base_url=STORAGE_SERVER_URL,
        cert=CERT,
        ca=CA,
    )


def init_crypto_context():
    """
    Запросит от пользователя пароль -> инициализирует KEK и DEK обратившись к сервису хранения
    :return:
    """
    passphrase = read_secret("Введите passphrase: ", "PASSPHRASE")

    kek = derive_kek(passphrase)
    del passphrase  # затираем passphrase

    storage = get_storage_client()

    try:
        payload = storage.get_secret_string(GLOBAL_DEK_NAME)

        try:
            dek = unwrap_dek(
                encrypted_data_b64=payload["encrypted_data"],
                nonce_b64=payload["nonce"],
                kek=kek,
            )
        except InvalidTag:
            raise CryptoInitializationError("Неверная passphrase")

        set_crypto_context(CryptoContext(kek=kek, dek=dek, nonce_b64_dek=payload["nonce"]))

    except StorageNotFound:
        dek = gen_key()  # 32 bytes
        encrypted_data, nonce, sha256 = wrap_dek(dek, kek)

        storage.create_secret_string(
            name=GLOBAL_DEK_NAME,
            encrypted_data=encrypted_data,
            nonce=nonce,
            sha256=sha256,
        )

        set_crypto_context(CryptoContext(kek=kek, dek=dek, nonce_b64_dek=nonce))


def check_storage_service() -> bool:
    storage = get_storage_client()
    try:
        storage.health()
        return True
    except StorageConnectionError:
        return False


def get_secret(secret_name: str) -> str:
    storage = get_storage_client()

    try:
        crypto = get_crypto_context()
    except RuntimeError:
        init_crypto_context()
        crypto = get_crypto_context()

    try:
        response = storage.get_secret_string(secret_name)

        secret = decrypt_text(
            encrypted_data_b64=response["encrypted_data"],
            nonce_b64=response["nonce"],
            dek=crypto.dek,
        )

    except StorageNotFound:
        secret = read_secret(f"Secret not Found.\nEnter {secret_name}: ", secret_name)

        encrypted_data, nonce, sha256 = encrypt_text(secret, crypto.dek)

        storage.create_secret_string(
            name=secret_name,
            encrypted_data=encrypted_data,
            nonce=nonce,
            sha256=sha256,
        )

    return secret




