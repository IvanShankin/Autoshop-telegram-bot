import hashlib
import os
import getpass
import sys
import warnings

from pathlib import Path
from argon2.low_level import hash_secret_raw, Type

from src.services.secrets.runtime import get_runtime

SALT = b"QJ\t\x11\xae\x94\x08\xb2\nP\x9fC\x87xpW"


def read_secret(prompt: str, name: str) -> str:
    """
    Безопасный ввод пароля.
    В реальном терминале используется getpass.
    В IDE используется метод input() с предупреждением.
    """
    runtime = get_runtime()
    if runtime.mode == "TEST":
        try:
            return os.getenv("MODE")
        except KeyError:
            raise RuntimeError(
                f"{name} must be set in test environment"
            )

    if sys.stdin.isatty():
        # Реальный терминал — безопасный ввод
        return getpass.getpass(prompt)

    warnings.warn(
        "Secure input is not supported in this environment. "
        "Password will be echoed. "
        "Run the program in a system terminal for secure input.",
        RuntimeWarning,
    )
    return input(prompt)


def derive_kek(passphrase: str, salt: bytes = SALT) -> bytes:
    """
    KEK (Key Encryption Key)
    Получаем из пароля.
    """
    return hash_secret_raw(
        secret=passphrase.encode(),
        salt=salt,
        time_cost=3,
        memory_cost=64 * 1024,  # 64 MB
        parallelism=2,
        hash_len=32,            # 256 bit
        type=Type.ID
    )


def gen_key(length: int = 32) -> bytes:
    """
    Генерирует криптографически стойкий Data Encryption Key (DEK).

    :param length: длина ключа в байтах (по умолчанию 32 = 256 бит)
    :return: bytes
    """
    return os.urandom(length)


def sha256_file(file_path: str | Path) -> str:
    """
    Считает SHA256 контрольную сумму файла и возвращает её в виде hex строки.
    """
    file_path = Path(file_path)
    h = hashlib.sha256()

    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)

    return h.hexdigest()