
class CryptoContext:
    __slots__ = ("kek", "dek", "nonce_b64_dek")

    def __init__(self, kek: bytes, dek: bytes, nonce_b64_dek: str):
        self.kek = kek
        self.dek = dek
        self.nonce_b64_dek = nonce_b64_dek


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


