from src.domain.crypto.models import CryptoContext


_CryptoContext: CryptoContext | None = None

def set_crypto_context(ctx: CryptoContext):
    """Временное решение, до перехода на clean architecture"""
    global _CryptoContext
    _CryptoContext = ctx


def get_crypto_context() -> CryptoContext:
    """Временное решение, до перехода на clean architecture"""
    global _CryptoContext
    return _CryptoContext