from pathlib import Path

import pytest
import tempfile
import zipfile
import os
from unittest.mock import patch



@pytest.mark.asyncio
async def test_extract_archive_to_temp_success():
    from src.services.filesystem.input_account import extract_archive_to_temp
    # создаём временный zip
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "test.zip")
        file_path = os.path.join(tmpdir, "file.txt")
        with open(file_path, "w") as f:
            f.write("hello")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(file_path, arcname="file.txt")

        extracted_dir = await extract_archive_to_temp(zip_path)
        assert os.path.exists(os.path.join(extracted_dir, "file.txt"))


@pytest.mark.asyncio
async def test_extract_archive_to_temp_invalid_zip():
    from src.services.filesystem.input_account import extract_archive_to_temp
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_zip = os.path.join(tmpdir, "bad.zip")
        with open(bad_zip, "w") as f:
            f.write("not a zip")
        with pytest.raises(RuntimeError):
            await extract_archive_to_temp(bad_zip)


@pytest.mark.asyncio
async def test_make_archive_success():
    from src.services.filesystem.input_account import make_archive
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "file.txt")
        with open(file_path, "w") as f:
            f.write("data")
        archive_path = os.path.join(tmpdir, "out.zip")
        result = await make_archive(tmpdir, archive_path)
        assert result
        assert os.path.exists(archive_path)


@pytest.mark.asyncio
async def test_make_archive_nonexistent_source():
    from src.services.filesystem.input_account import make_archive
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, "out.zip")
        result = await make_archive("/nonexistent/path", archive_path)
        assert result is False


@pytest.mark.asyncio
async def test_encrypted_tg_account_success(tmp_path):
    from src.services.filesystem.input_account import encrypted_tg_account
    src_dir = tmp_path / "account"
    src_dir.mkdir()
    (src_dir / "file.txt").write_text("test")

    dest_path = tmp_path / "encrypted.zip"

    def fake_encrypt_folder(folder_path, encrypted_path, key):
        # создаём пустой файл, чтобы sha256_file не падал
        Path(encrypted_path).write_text("encrypted")

    with patch("src.services.filesystem.input_account.make_account_key", return_value=("key_b64", b"key", "nonce")):
        with patch("src.services.filesystem.input_account.encrypt_folder", side_effect=fake_encrypt_folder) as mock_encrypt:
            result = await encrypted_tg_account(str(src_dir), str(dest_path))
            mock_encrypt.assert_called_once()
            assert result.result
            assert result.path_encrypted_acc == str(dest_path)




@pytest.mark.asyncio
async def test_archive_if_not_empty_creates_archive(tmp_path):
    from src.services.filesystem.input_account import archive_if_not_empty
    d = tmp_path / "folder"
    d.mkdir()
    (d / "file.txt").write_text("data")

    archive_path = await archive_if_not_empty(str(d))
    assert archive_path is not None
    assert os.path.exists(archive_path)


@pytest.mark.asyncio
async def test_archive_if_not_empty_empty_dir(tmp_path):
    from src.services.filesystem.input_account import archive_if_not_empty
    d = tmp_path / "empty"
    d.mkdir()
    archive_path = await archive_if_not_empty(str(d))
    assert archive_path is None



@pytest.mark.asyncio
async def test_cleanup_used_data(tmp_path):
    from src.services.filesystem.input_account import cleanup_used_data
    # создаём папки и файлы
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    file1 = base_dir / "f1.txt"
    file1.write_text("123")

    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    (invalid_dir / "bad.txt").write_text("x")

    duplicate_dir = tmp_path / "dup"
    duplicate_dir.mkdir()
    (duplicate_dir / "dup.txt").write_text("y")

    archive_path = tmp_path / "archive.zip"
    archive_path.write_text("zip")

    all_items = [type("Item", (), {"dir_path": str(base_dir)})()]

    await cleanup_used_data(
        archive_path=str(archive_path),
        base_dir=str(base_dir),
        invalid_dir=str(invalid_dir),
        duplicate_dir=str(duplicate_dir),
        invalid_archive=None,
        duplicate_archive=None,
        all_items=all_items
    )

    # проверяем что все удалилось
    assert not base_dir.exists()
    assert not invalid_dir.exists()
    assert not duplicate_dir.exists()
    assert not archive_path.exists()



def test_make_csv_bytes_happy_path():
    from src.services.filesystem.input_account import make_csv_bytes
    data = [
        {"phone": "+79991234567", "login": "user1", "password": "p1"},
        {"phone": "+380501234567", "login": "user2", "password": "p2"},
    ]

    b = make_csv_bytes(data, ['phone', 'login', 'password'])
    assert isinstance(b, (bytes, bytearray))

    text = b.decode("utf-8")
    # Заголовки должны быть в тексте
    assert "phone" in text and "login" in text and "password" in text
    # Данные также должны присутствовать
    assert "+79991234567" in text
    assert "user2" in text


def test_make_csv_bytes_empty_raises():
    from src.services.filesystem.input_account import make_csv_bytes
    with pytest.raises(ValueError):
        make_csv_bytes([], [])