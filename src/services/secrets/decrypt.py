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


def unwrap_dek(encrypted_key_b64: str, kek: bytes) -> bytes:
    wrapped = base64.b64decode(encrypted_key_b64)
    return decrypt_bytes(wrapped, kek)


def decrypt_text(encrypted_b64: str, dek: bytes) -> str:
    """
    Расшифровывает base64(nonce || ciphertext) в строку
    """
    wrapped = base64.b64decode(encrypted_b64)

    nonce = wrapped[:12]
    ct = wrapped[12:]

    aesgcm = AESGCM(dek)
    plaintext = aesgcm.decrypt(nonce, ct, None)

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

