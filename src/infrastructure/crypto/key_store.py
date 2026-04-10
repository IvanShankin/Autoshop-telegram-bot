import base64
from asyncio import Protocol

import keyring


class KeyStore(Protocol):

    def __init__(self):
        self.SERVICE_NAME = "auto_shop"
        self.KEK_KEY = "crypto_kek"

    def load_kek(self) -> bytes:
        """Загружает kek из защищённого хранилища (локальное)"""
        kek_b64 = keyring.get_password(self.SERVICE_NAME, self.KEK_KEY)
        if not kek_b64:
            raise RuntimeError("KEK not found in OS keyring")
        return base64.b64decode(kek_b64)

    def store_kek(self, kek: bytes) -> None:
        """Устанавливает kek в защищённое хранилище (локальное)"""
        keyring.set_password(
            self.SERVICE_NAME,
            self.KEK_KEY,
            base64.b64encode(kek).decode(),
        )
