from src.services.secrets.decrypt import unwrap_dek
from src.services.secrets.utils import read_passphrase, derive_kek


class CryptoContext:
    __slots__ = ("kek", "dek")

    def __init__(self, kek: bytes, dek: bytes):
        self.kek = kek
        self.dek = dek


_CRYPTO_CTX: CryptoContext | None = None


def set_crypto_context(ctx: CryptoContext):
    global _CRYPTO_CTX
    if _CRYPTO_CTX is not None:
        raise RuntimeError("CryptoContext already set")
    _CRYPTO_CTX = ctx


def get_crypto_context() -> CryptoContext:
    if _CRYPTO_CTX is None:
        raise RuntimeError("CryptoContext not initialized")
    return _CRYPTO_CTX


def init_crypto_context() -> CryptoContext:
    passphrase = read_passphrase()

    kek = derive_kek(passphrase)

    del passphrase # затираем passphrase

    enc_dek = b"fdsfdsvxx"# обращаемся к API и получаем зашифрованный DEK
    dek = unwrap_dek(enc_dek, kek)

    return CryptoContext(kek=kek, dek=dek)
