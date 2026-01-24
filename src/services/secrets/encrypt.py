import hashlib
import os
import base64
import shutil
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM



def encrypt_bytes(plaintext: bytes, dek: bytes) -> bytes:
    """
        Зашифрует строку байт, указанным ключом
        :param dek: Для шифрования всех данных передавать DEK
    """
    aesgcm = AESGCM(dek)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def wrap_dek(dek: bytes, kek: bytes) -> tuple[str, str, str]:
    """
    Шифрует DEK с помощью KEK.
    Возвращает:
    encrypted_data_b64, nonce_b64, sha256_b64
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(kek)

    ciphertext = aesgcm.encrypt(nonce, dek, None)
    sha256 = hashlib.sha256(ciphertext).digest()

    return (
        base64.b64encode(ciphertext).decode("ascii"),
        base64.b64encode(nonce).decode("ascii"),
        base64.b64encode(sha256).decode("ascii"),
    )


def encrypt_text(plaintext: str, dek: bytes, nonce_b64:  bytes = None) -> tuple[str, str, str]:
    """
    Возвращает:
    encrypted_data_b64, nonce_b64, sha256_b64
    """
    data = plaintext.encode("utf-8")

    if not nonce_b64:
        nonce_b64 = os.urandom(12)

    aesgcm = AESGCM(dek)

    ciphertext = aesgcm.encrypt(nonce_b64, data, None)

    sha256 = hashlib.sha256(ciphertext).digest()

    return (
        base64.b64encode(ciphertext).decode("ascii"),
        base64.b64encode(nonce_b64).decode("ascii"),
        base64.b64encode(sha256).decode("ascii"),
    )


def make_account_key(kek: bytes) -> tuple[str, bytes, str]:
    """
    Создаёт DEK (account_key)
    :return: Tuple[
        encrypted_dek_b64 — зашифрованный DEK (для storage),
        account_key — plaintext DEK (для runtime),
        nonce_b64 — используемый nonce для шифрования
    ]
    """
    account_key = os.urandom(32)  # plaintext DEK
    nonce = os.urandom(12)        # уникальный nonce для AES-GCM

    aesgcm = AESGCM(kek)
    encrypted = aesgcm.encrypt(nonce, account_key, None)

    encrypted_dek_b64 = base64.b64encode(encrypted).decode("ascii")
    nonce_b64 = base64.b64encode(nonce).decode("ascii")

    return encrypted_dek_b64, account_key, nonce_b64


def encrypt_folder(folder_path: str, encrypted_path: str, dek: bytes):
    """Архивирует папку и шифрует архив. Удалит folder_path"""
    # создаём имя временного файла, но не открываем его
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_zip_path = tmp.name

    # архивируем
    shutil.make_archive(tmp_zip_path.replace(".zip", ""), 'zip', folder_path)

    # читаем данные архива
    with open(tmp_zip_path, "rb") as f:
        data = f.read()

    # шифруем
    encrypted = encrypt_bytes(data, dek)

    # записываем зашифрованный файл
    with open(encrypted_path, "wb") as f:
        f.write(encrypted)

    # очищаем
    os.remove(tmp_zip_path)
    shutil.rmtree(folder_path)


def encrypt_file(
    file_path: str,
    encrypted_path: str,
    dek: bytes,
):
    """
    Открывает файл полностью!!! Использовать только для небольших файлов
    :param file_path: Путь к незашифрованному файлу
    :param encrypted_path: новый путь к зашифрованному файлу
    :return:
    """
    with open(file_path, "rb") as f:
        data = f.read()

    encrypted_dir = os.path.dirname(encrypted_path)
    if encrypted_dir:  # Проверяем, что путь содержит директорию
        os.makedirs(encrypted_dir, exist_ok=True)

    encrypted = encrypt_bytes(data, dek)

    with open(encrypted_path, "wb") as f:
        f.write(encrypted)
