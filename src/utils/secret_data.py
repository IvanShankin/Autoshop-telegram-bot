import os
import base64
import shutil
import tempfile
import zipfile

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config import SECRET_KEY

key = base64.urlsafe_b64encode(SECRET_KEY.encode().ljust(32, b'0')[:32])
fernet = Fernet(key)

def encrypt_token(text: str) -> str:
    """Шифрует переданный текст"""
    return fernet.encrypt(text.encode()).decode()

def decrypt_token(text_encrypted: str) -> str:
    """Расшифровывает переданный зашифрованный текст"""
    return fernet.decrypt(text_encrypted.encode()).decode()

def derive_master_key() -> bytes:
    return base64.b64decode(SECRET_KEY)

def decrypt_bytes_with_key(nonce_and_ct: bytes, key: bytes) -> bytes:
    nonce = nonce_and_ct[:12]
    ct = nonce_and_ct[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, associated_data=None)

def unwrap_account_key(wrapped_b64: str, master_key: bytes) -> bytes:
    wrapped = base64.b64decode(wrapped_b64)
    return decrypt_bytes_with_key(wrapped, master_key)

def decrypt_file_to_bytes(src_path: str, key: bytes) -> bytes:
    with open(src_path, "rb") as f:
        wrapped = f.read()
    return decrypt_bytes_with_key(wrapped, key)

def gen_key() -> bytes:
    """Генерирует рандомный ключ из строки бит, длинной в 256 символов"""
    return os.urandom(32)  # 256-bit AES key

def encrypt_bytes_with_key(plaintext: bytes, key: bytes) -> bytes:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def encrypt_folder(folder_path: str, encrypted_path: str, key: bytes):
    """Архивирует папку и шифрует архив."""
    # создаём имя временного файла, но не открываем его
    tmp_zip_path = tempfile.mktemp(suffix=".zip")

    # архивируем
    shutil.make_archive(tmp_zip_path.replace(".zip", ""), 'zip', folder_path)

    # читаем данные архива
    with open(tmp_zip_path, "rb") as f:
        data = f.read()

    # шифруем
    encrypted = encrypt_bytes_with_key(data, key)

    # записываем зашифрованный файл
    with open(encrypted_path, "wb") as f:
        f.write(encrypted)

    # очищаем
    os.remove(tmp_zip_path)
    shutil.rmtree(folder_path)

def decrypt_folder(encrypted_path: str, key: bytes) -> str:
    """Расшифровывает зашифрованный архив во временную папку и возвращает путь к ней."""
    with open(encrypted_path, "rb") as f:
        encrypted_data = f.read()

    decrypted_data = decrypt_bytes_with_key(encrypted_data, key)

    tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp_zip.write(decrypted_data)
    tmp_zip.close()

    extract_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(tmp_zip.name, "r") as zf:
        zf.extractall(extract_dir)

    os.remove(tmp_zip.name)
    return extract_dir