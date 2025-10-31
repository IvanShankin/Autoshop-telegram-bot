import os
import base64
import pytest
from pathlib import Path

from src.utils.secret_data import encrypt_token, decrypt_token, gen_key, encrypt_bytes_with_key, decrypt_bytes_with_key, \
    unwrap_account_key, decrypt_file_to_bytes, encrypt_folder, decrypt_folder


@pytest.mark.asyncio
async def test_encrypt_decrypt_token_roundtrip():
    text = "my_secret_text"
    enc = encrypt_token(text)
    dec = decrypt_token(enc)
    assert dec == text
    assert enc != text


def test_gen_key_length_and_uniqueness():
    k1 = gen_key()
    k2 = gen_key()
    assert len(k1) == 32
    assert len(k2) == 32
    assert k1 != k2  # вероятность совпадения крайне мала


def test_encrypt_decrypt_bytes_roundtrip():
    key = gen_key()
    plaintext = b"hello world"
    enc = encrypt_bytes_with_key(plaintext, key)
    dec = decrypt_bytes_with_key(enc, key)
    assert dec == plaintext


def test_decrypt_bytes_with_wrong_key_raises():
    key1 = gen_key()
    key2 = gen_key()
    plaintext = b"test-data"
    encrypted = encrypt_bytes_with_key(plaintext, key1)
    with pytest.raises(Exception):
        decrypt_bytes_with_key(encrypted, key2)


def test_unwrap_account_key_and_file_decrypt(tmp_path):
    key = gen_key()
    plaintext = b"super data"
    encrypted = encrypt_bytes_with_key(plaintext, key)
    wrapped_b64 = base64.b64encode(encrypted).decode()

    # unwrap_account_key
    unwrapped = unwrap_account_key(wrapped_b64, key)
    assert unwrapped == plaintext

    # decrypt_file_to_bytes
    file_path = tmp_path / "encrypted.bin"
    with open(file_path, "wb") as f:
        f.write(encrypted)
    decrypted = decrypt_file_to_bytes(str(file_path), key)
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
