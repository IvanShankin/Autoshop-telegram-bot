import base64
import keyring


SERVICE_NAME = "auto_shop"
KEK_KEY = "crypto_kek"


def store_kek(kek: bytes) -> None:
    """Устанавливает kek в защищённое хранилище (локальное)"""
    keyring.set_password(
        SERVICE_NAME,
        KEK_KEY,
        base64.b64encode(kek).decode(),
    )


def load_kek() -> bytes:
    """Загружает kek из защищённого хранилища (локальное)"""
    kek_b64 = keyring.get_password(SERVICE_NAME, KEK_KEY)
    if not kek_b64:
        raise RuntimeError("KEK not found in OS keyring")
    return base64.b64decode(kek_b64)
