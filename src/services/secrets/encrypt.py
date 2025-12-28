import os
import base64
import shutil
import tempfile
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


def wrap_dek(dek: bytes, kek: bytes) -> str:
    wrapped = encrypt_bytes(dek, kek)
    return base64.b64encode(wrapped).decode()


def encrypt_text(plaintext: str, dek: bytes) -> str:
    """
       Шифрует текст с помощью DEK.
       Возвращает base64(nonce || ciphertext)
       """
    data = plaintext.encode("utf-8")

    aesgcm = AESGCM(dek)
    nonce = os.urandom(12)

    ciphertext = aesgcm.encrypt(nonce, data, None)
    wrapped = nonce + ciphertext

    return base64.b64encode(wrapped).decode("ascii")


def make_account_key(kek: bytes) -> tuple[str, bytes]:
    """
    Создаёт DEK (account_key)
    :return: Tuple[encrypted_dek_b64 — зашифрованный DEK (для storage), account_key — plaintext DEK (для runtime)]
    """
    account_key = os.urandom(32)  # DEK

    aesgcm = AESGCM(kek)
    nonce = os.urandom(12)
    encrypted = aesgcm.encrypt(nonce, account_key, None)

    wrapped = nonce + encrypted
    encrypted_key_b64 = base64.b64encode(wrapped).decode()

    return encrypted_key_b64, account_key


def encrypt_folder(folder_path: str, encrypted_path: str, dek: bytes):
    """Архивирует папку и шифрует архив. Удалит folder_path"""
    # создаём имя временного файла, но не открываем его
    tmp_zip_path = tempfile.mktemp(suffix=".zip")

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
