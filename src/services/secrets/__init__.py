from src.services.secrets.client import SecretsStorageClient
from src.services.secrets.crypto import CryptoContext, set_crypto_context, get_crypto_context
from src.services.secrets.decrypt import decrypt_bytes, decrypt_text, unwrap_dek, decrypt_file_to_bytes, decrypt_folder
from src.services.secrets.encrypt import encrypt_bytes, wrap_dek, encrypt_text, make_account_key, encrypt_folder
from src.services.secrets.loader import init_crypto_context
from src.services.secrets.utils import read_secret, derive_kek, gen_key, sha256_file

__all__ = [
    # client
    "SecretsStorageClient",

    # crypto.py
    "CryptoContext",
    "set_crypto_context",
    "get_crypto_context",
    "init_crypto_context",

    # utils.py
    "read_secret",
    "derive_kek",
    "gen_key",
    "sha256_file",

    # encrypt
    "encrypt_bytes",
    "wrap_dek",
    "encrypt_text",
    "make_account_key",
    "encrypt_folder",

    # decrypt
    "decrypt_bytes",
    "unwrap_dek",
    "decrypt_text",
    "decrypt_file_to_bytes",
    "decrypt_folder",
]