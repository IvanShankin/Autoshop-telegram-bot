"""
Инфраструктурные исключения.
Исключения, связанные с внешними сервисами и инфраструктурой.
"""

class TelegramError(Exception):
    """Любая ошибка связанная с Telethon"""
    pass

class CryptoInitializationError(RuntimeError):
    """При вводе оператором неверный passphrase"""
    pass

class StorageError(RuntimeError):
    pass

class StorageConnectionError(StorageError):
    """При ошибки подключения к сервису хранения"""
    pass

class StorageSSLError(StorageError):
    """Ошибка mTLS: неверный клиентский сертификат или CA при взаимодействии с сервисом хранения"""
    pass

class StorageNotFound(StorageError):
    """При возвращении ошибки 404 от сервиса хранения"""
    pass

class StorageGone(StorageError):
    """При возвращении ошибки 410 от сервиса хранения"""
    pass

class StorageConflict(StorageError):
    """При возвращении ошибки 409 от сервиса хранения"""
    pass

class StorageResponseError(StorageError):
    """Любая ошибка от сервиса хранения которая не описана другим исключением"""
    def __init__(self, status_code: int, body: str | None = None):
        self.status_code = status_code
        super().__init__(f"Storage returned HTTP {status_code}: {body}")