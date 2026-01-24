import asyncio
import csv
import io
import shutil
from pathlib import Path
from typing import Optional, List, Sequence, Dict

from src.services.filesystem.actions import _sync_cleanup_used_data
from src.services.products.accounts.tg.shemas import CreatedEncryptedArchive, BaseAccountProcessingResult
from src.utils.core_logger import get_logger
from src.services.secrets import encrypt_folder, make_account_key, sha256_file, get_crypto_context


async def encrypted_tg_account(
    src_directory: str,
    dest_encrypted_path: str
) -> CreatedEncryptedArchive:
    """
    Шифрует данные TG аккаунта в указанный путь.
    Ключ генерируется здесь, путь НЕ генерируется.
    """

    try:
        crypto = get_crypto_context()
        encrypted_key_b64, account_key, nonce = make_account_key(crypto.kek)

        # создаём директорию под файл
        Path(dest_encrypted_path).parent.mkdir(parents=True, exist_ok=True)

        # шифруем
        encrypt_folder(
            folder_path=src_directory,
            encrypted_path=dest_encrypted_path,
            dek=account_key
        )

        # считаем checksum
        checksum = sha256_file(dest_encrypted_path)

        return CreatedEncryptedArchive(
            result=True,
            encrypted_key_b64=encrypted_key_b64,
            path_encrypted_acc=dest_encrypted_path,
            encrypted_key_nonce=nonce,
            checksum=checksum
        )

    except Exception as e:
        logger = get_logger(__name__)
        logger.exception(f"Ошибка при шифровании: {e}")
        return CreatedEncryptedArchive(result=False)


#  безопасная архивирующая функция (не блокирует loop)
async def archive_if_not_empty(directory: str) -> Optional[str]:
    dir_path = Path(directory)
    if not dir_path.exists():
        return None
    # проверяем наличие любых элементов
    if not any(dir_path.iterdir()):
        return None
    # вызов blocking make_archive в thread
    archive_path = await asyncio.to_thread(
        shutil.make_archive,
        str(dir_path),  # base_name
        "zip",
        str(dir_path)   # root_dir
    )
    return archive_path


# --- Асинхронная-обёртка (вызывать в async коде) ---
async def cleanup_used_data(
    archive_path: Optional[str],
    base_dir: Optional[str],
    invalid_dir: Optional[str],
    duplicate_dir: Optional[str],
    invalid_archive: Optional[str],
    duplicate_archive: Optional[str],
    all_items: List[BaseAccountProcessingResult],
):
    item_dirs = [getattr(it, "dir_path", None) for it in all_items]
    await asyncio.to_thread(
        _sync_cleanup_used_data,
        archive_path,
        base_dir,
        invalid_dir,
        duplicate_dir,
        invalid_archive,
        duplicate_archive,
        item_dirs
    )


def make_csv_bytes(
    data: Sequence[Dict[str, str]],
    headers: Sequence[str],
    *,
    excel_compatible: bool = True,
    encoding: str = "utf-8"
) -> bytes:
    """
    Создаёт CSV в памяти и возвращает bytes.
    По умолчанию делает excel_compatible CSV (delimiter=';' + BOM),
    чтобы Excel корректно открыл файл в большинстве локалей.
    """
    if not data or not headers:
        raise ValueError("Data is empty")

    # text stream для csv.writer (работаем с текстом)
    stream = io.StringIO()
    delimiter = ";" if excel_compatible else ","

    writer = csv.DictWriter(stream, fieldnames=list(headers), delimiter=delimiter, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)

    text = stream.getvalue()

    # Для Excel лучше отдавать BOM (utf-8-sig)
    if excel_compatible:
        return text.encode("utf-8-sig")
    else:
        return text.encode(encoding)