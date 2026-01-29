import os
import base64
import tempfile
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def decrypt_bytes(nonce_and_ct: bytes, dek: bytes) -> bytes:
    """
        Расшифрует строку байт, указанным ключом
        :param dek: Для дешифрования всех данных передавать DEK
    """
    nonce = nonce_and_ct[:12]
    ct = nonce_and_ct[12:]
    aesgcm = AESGCM(dek)
    return aesgcm.decrypt(nonce, ct, None)


def unwrap_dek(
    encrypted_data_b64: str,
    nonce_b64: str,
    kek: bytes,
) -> bytes:
    ciphertext = base64.b64decode(encrypted_data_b64)
    nonce = base64.b64decode(nonce_b64)

    aesgcm = AESGCM(kek)
    return aesgcm.decrypt(nonce, ciphertext, None)


def decrypt_text(
    encrypted_data_b64: str,
    nonce_b64: str,
    dek: bytes,
) -> str:
    ciphertext = base64.b64decode(encrypted_data_b64)
    nonce = base64.b64decode(nonce_b64)

    aesgcm = AESGCM(dek)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return plaintext.decode("utf-8")


def decrypt_file_to_bytes(src_path: str, dek: bytes) -> bytes:
    with open(src_path, "rb") as f:
        wrapped = f.read()
    return decrypt_bytes(wrapped, dek)


def decrypt_folder(encrypted_path: str, dek: bytes) -> str:
    """Расшифровывает зашифрованный архив во временную папку и возвращает путь к ней."""
    with open(encrypted_path, "rb") as f:
        encrypted_data = f.read()

    decrypted_data = decrypt_bytes(encrypted_data, dek)

    tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp_zip.write(decrypted_data)
    tmp_zip.close()

    extract_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(tmp_zip.name, "r") as zf:
        zf.extractall(extract_dir)

    os.remove(tmp_zip.name)
    return extract_dir


def decrypt_file(
    dek: bytes,
    encrypted_path: str,
    decrypted_path: str,
):
    """
    Дешифрует файл. Открывает файл полностью!
    :param encrypted_path: Путь к зашифрованному файлу
    :param decrypted_path: Путь к файлу который будет создан после дешифрации
    :return:
    """
    with open(encrypted_path, "rb") as f:
        encrypted_data = f.read()

    decrypted_data = decrypt_bytes(encrypted_data, dek)

    decrypted_dir = os.path.dirname(decrypted_path)
    if decrypted_dir:  # Проверяем, что путь содержит директорию
        os.makedirs(decrypted_dir, exist_ok=True)

    with open(decrypted_path, "wb") as f:
        f.write(decrypted_data)
