import os
import base64
import pytest
from pathlib import Path

from src.services.secrets import encrypt_text, decrypt_text, gen_key, encrypt_bytes, \
    decrypt_bytes, \
    decrypt_file_to_bytes, encrypt_folder, decrypt_folder, get_crypto_context, unwrap_dek


@pytest.mark.asyncio
async def test_encrypt_decrypt_token_roundtrip():
    text = "my_secret_text"

    crypto = get_crypto_context()

    enc = encrypt_text(text, crypto.dek)
    dec = decrypt_text(enc, crypto.dek)

    assert dec == text
    assert enc != text


def test_gen_key_length_and_uniqueness():
    k1 = gen_key()
    k2 = gen_key()
    assert len(k1) == 32
    assert len(k2) == 32
    assert k1 != k2  # вероятность совпадения крайне мала


def test_encrypt_decrypt_text_roundtrip():
    dek = gen_key()
    plaintext = b"hello world"
    enc = encrypt_bytes(plaintext, dek)
    dec = decrypt_bytes(enc, dek)
    assert dec == plaintext


def test_decrypt_text_with_wrong_key_raises():
    key1 = gen_key()
    key2 = gen_key()
    plaintext = b"test-data"
    encrypted = encrypt_bytes(plaintext, key1)
    with pytest.raises(Exception):
        decrypt_bytes(encrypted, key2)


def test_unwrap_account_key_and_file_decrypt(tmp_path):
    crypto = get_crypto_context()
    plaintext = b"super data"
    encrypted = encrypt_bytes(plaintext, crypto.dek)
    wrapped_b64 = base64.b64encode(encrypted).decode()

    unwrapped = unwrap_dek(wrapped_b64, crypto.dek)
    assert unwrapped == plaintext

    # decrypt_file_to_bytes
    file_path = tmp_path / "encrypted.bin"
    with open(file_path, "wb") as f:
        f.write(encrypted)
    decrypted = decrypt_file_to_bytes(str(file_path), crypto.dek)
    assert decrypted == plaintext


def test_encrypt_decrypt_folder(tmp_path):
    # создаём тестовую папку с файлами
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file1.txt").write_text("hello")
    (folder / "file2.txt").write_text("world")

    key = gen_key()
    encrypted_path = tmp_path / "folder.enc"

    encrypt_folder(str(folder), str(encrypted_path), key)

    # после шифрования папка должна быть удалена
    assert not folder.exists()
    assert encrypted_path.exists()

    # дешифруем обратно
    decrypted_dir = decrypt_folder(str(encrypted_path), key)

    # проверяем файлы
    restored_files = sorted(os.listdir(decrypted_dir))
    assert restored_files == ["file1.txt", "file2.txt"]

    file1_content = Path(decrypted_dir, "file1.txt").read_text()
    file2_content = Path(decrypted_dir, "file2.txt").read_text()
    assert file1_content == "hello"
    assert file2_content == "world"


def test_decrypt_folder_with_wrong_key_raises(tmp_path):
    folder = tmp_path / "f"
    folder.mkdir()
    (folder / "x.txt").write_text("data")
    key1 = gen_key()
    key2 = gen_key()

    encrypted_path = tmp_path / "f.enc"
    encrypt_folder(str(folder), str(encrypted_path), key1)

    with pytest.raises(Exception):
        decrypt_folder(str(encrypted_path), key2)
