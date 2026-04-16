import os
import pytest
from pathlib import Path

from src.domain.crypto.decrypt import decrypt_text, decrypt_bytes, decrypt_file_to_bytes, decrypt_folder
from src.domain.crypto.encrypt import encrypt_bytes, encrypt_folder, wrap_dek
from src.domain.crypto.key_ops import encrypt_text, unwrap_dek
from src.domain.crypto.utils import gen_key
from src.infrastructure.files.file_system import create_temp_dir


@pytest.mark.asyncio
async def test_encrypt_decrypt_token_roundtrip(container_fix):
    text = "my_secret_text"

    crypto = container_fix.crypto_provider.get()

    enc, nonce_b64, _ = encrypt_text(text, crypto.dek)
    dec = decrypt_text(enc, nonce_b64, crypto.dek)

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


def test_unwrap_account_key_and_file_decrypt(container_fix):
    temp_dir = create_temp_dir(container_fix.config)
    crypto = container_fix.crypto_provider.get()
    plaintext = b"super data"

    wrapped_b64, nonce_b64, _ = wrap_dek(plaintext, crypto.kek)
    unwrapped = unwrap_dek(wrapped_b64, nonce_b64, crypto.kek)
    assert unwrapped == plaintext

    # decrypt_file_to_bytes
    file_path = temp_dir / "encrypted.bin"
    encrypted = encrypt_bytes(plaintext, crypto.dek)
    with open(file_path, "wb") as f:
        f.write(encrypted)

    decrypted = decrypt_file_to_bytes(str(file_path), crypto.dek)

    assert decrypted == plaintext


def test_encrypt_decrypt_folder(container_fix):
    # создаём тестовую папку с файлами
    temp_dir = create_temp_dir(container_fix.config)
    folder = temp_dir / "folder"
    folder.mkdir()
    (folder / "file1.txt").write_text("hello")
    (folder / "file2.txt").write_text("world")

    key = gen_key()
    encrypted_path = temp_dir / "folder.enc"

    encrypt_folder(str(folder), str(encrypted_path), key)

    # после шифрования папка должна быть удалена
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


def test_decrypt_folder_with_wrong_key_raises(container_fix):
    temp_dir = create_temp_dir(container_fix.config)
    folder = temp_dir / "f"
    folder.mkdir()
    (folder / "x.txt").write_text("data")
    key1 = gen_key()
    key2 = gen_key()

    encrypted_path = temp_dir / "f.enc"
    encrypt_folder(str(folder), str(encrypted_path), key1)

    with pytest.raises(Exception):
        decrypt_folder(str(encrypted_path), key2)
