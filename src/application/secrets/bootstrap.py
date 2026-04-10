from getpass import getpass

from src.application.crypto.crypto_context import GLOBAL_DEK_NAME
from src.application.crypto.secrets_storage import get_storage_client
from src.config import EnvSettings, PathSettings, init_env
from src.domain.crypto.key_ops import encrypt_text
from src.exceptions import StorageNotFound, StorageConflict
from src.application.secrets import get_crypto_context, set_crypto_context, CryptoContext, unwrap_dek
from src.application.secrets._runtime import set_runtime, RuntimeMode, SecretsRuntime
from src.domain.crypto.utils import derive_kek, gen_key
from src.domain.crypto.encrypt import wrap_dek
from src.application.secrets._keyring_store import store_kek



def bootstrap():
    init_dek()
    set_secrets()

def _encrypt_input(secret_name: str, dek: bytes) -> tuple[str, str, str]:
    secret = read_secret(f"Enter secret {secret_name}: ", secret_name)
    return encrypt_text(secret, dek)

def _init_runtime():
    init_env()

    env = EnvSettings.from_env()
    paths = PathSettings.build(env.use_secret_storage)

    set_runtime(
        SecretsRuntime(
            mode=RuntimeMode(env.mode),
            storage_url=env.storage_server_url,
            cert=(
                str(paths.ssl_client_cert_file),
                str(paths.ssl_client_key_file),
            ),
            ca=str(paths.ssl_ca_file),
        )
    )

def init_dek() -> bytes:
    """
    Запрашивает passphrase и установит dek
    """
    passphrase = getpass("Enter master passphrase: ")
    kek = derive_kek(passphrase)
    del passphrase

    store_kek(kek) # установка kek

    _init_runtime()

    storage = get_storage_client()

    try:
        response = storage.get_secret_string(GLOBAL_DEK_NAME)
        enc_dek = response["encrypted_data"]
        nonce = response["nonce"]
        print("Global DEK already exists")
    except StorageNotFound:
        dek = gen_key()
        enc_dek, nonce, sha256 = wrap_dek(dek, kek)

        storage.create_secret_string(
            name=GLOBAL_DEK_NAME,
            encrypted_data=enc_dek,
            nonce=nonce,
            sha256=sha256,
        )

        print("Global DEK created")

    dek = unwrap_dek(enc_dek, nonce, kek)

    set_crypto_context(
        CryptoContext(
            kek=kek,
            dek=dek,
            nonce_b64_dek=nonce
        )
    )

    return kek


def set_secrets():
    storage = get_storage_client()
    secrets_names = SecretSettings.model_fields.keys()
    crypto = get_crypto_context()

    for secret_name in secrets_names:
        try:
            storage.get_secret_string(secret_name)
            while True:
                response_user = input(
                    f"Secret {secret_name} exists, overwrite? (Y/N)"
                ).strip().lower()
                if response_user in {"y", "n"}:
                    break

                print("Please enter 'y' or 'n'")

            if response_user == "y":
                encrypted_data, nonce, sha256 = _encrypt_input(secret_name, crypto.dek)

                storage.create_next_string_version(
                    name=secret_name,
                    encrypted_data=encrypted_data,
                    nonce=nonce,
                    sha256=sha256,
                )
            elif response_user == "n":
                print(f"Secret {secret_name} skipped")

        except StorageNotFound:
            encrypted_data, nonce, sha256 = _encrypt_input(secret_name, crypto.dek)

            try:
                storage.create_secret_string(
                    name=secret_name,
                    encrypted_data=encrypted_data,
                    nonce=nonce,
                    sha256=sha256,
                )
            except StorageConflict: # если секрет помечен как удалённый в БД
                storage.purge_secret(
                    name=secret_name,
                )

                storage.create_secret_string(
                    name=secret_name,
                    encrypted_data=encrypted_data,
                    nonce=nonce,
                    sha256=sha256,
                )


if __name__ == "__main__":
    bootstrap()
