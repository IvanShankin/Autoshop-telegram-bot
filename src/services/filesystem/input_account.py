import asyncio
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, List

from src.services.tg_accounts.shemas import CreatedEncryptedArchive, BaseAccountProcessingResult
from src.utils.core_logger import logger
from src.utils.secret_data import encrypt_folder, make_account_key, sha256_file


async def extract_archive_to_temp(archive_path: str) -> str:
    """
    Распаковывает только zip архив в temp директорию.
    Возвращает путь к temp папке.
    """
    temp_dir = tempfile.mkdtemp()

    # при расширении тут можно добавить больше типов архивов
    try:
        with zipfile.ZipFile(archive_path, 'r') as z:
            z.extractall(temp_dir)
        return temp_dir
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Ошибка распаковки архива: {e}")


async def make_archive(data_for_archiving: str, new_path_archive: str) -> bool:
    """
    Создает архив из указанных данных

    :param data_for_archiving: путь к данным (файл или директория)
    :param new_path_archive: путь где создастся архив (файл или директория)
    :return: bool: результат операции
    """
    try:
        if not os.path.exists(data_for_archiving):
            logger.error(f"Ошибка: путь '{data_for_archiving}' не существует")
            return False

        # Преобразуем new_path_archive → гарантированно .zip-файл
        archive_file = ensure_zip_path(new_path_archive)

        # Создаём директорию ПОД ФАЙЛ
        archive_dir = archive_file.parent
        archive_dir.mkdir(parents=True, exist_ok=True)

        return await _create_zip_archive(data_for_archiving, str(archive_file))

    except Exception as e:
        logger.exception(f"Ошибка make_archive: {e}")
        return False


def ensure_zip_path(path: str | Path) -> Path:
    """Гарантирует, что путь указывает на файл .zip, а не на директорию."""
    path = Path(path)

    if path.exists() and path.is_dir():
        return path.with_suffix(".zip")

    if path.suffix.lower() != ".zip":
        return path.with_suffix(".zip")

    return path


async def _create_zip_archive(source_path: str, archive_path: str) -> bool:
    """Создает ZIP архив"""
    try:
        # Запускаем в отдельном потоке чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_create_zip, source_path, archive_path)
        return True
    except Exception as e:
        logger.exception(f"Ошибка при создании ZIP архива: {e}")
        return False


def _sync_create_zip(source_path: str, archive_path: str):
    """Синхронное создание ZIP архива"""
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.isfile(source_path):
            # Архивируем один файл
            zipf.write(source_path, os.path.basename(source_path))
        else:
            # Архивируем директорию
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=os.path.dirname(source_path))
                    zipf.write(file_path, arcname)


async def encrypted_tg_account(
    src_directory: str,
    dest_encrypted_path: str
) -> CreatedEncryptedArchive:
    """
    Шифрует данные TG аккаунта в указанный путь.
    Ключ генерируется здесь, путь НЕ генерируется.
    """

    try:
        encrypted_key_b64, account_key, nonce_b64 = make_account_key()

        # создаём директорию под файл
        Path(dest_encrypted_path).parent.mkdir(parents=True, exist_ok=True)

        # шифруем
        encrypt_folder(
            folder_path=src_directory,
            encrypted_path=dest_encrypted_path,
            key=account_key
        )

        # считаем checksum
        checksum = sha256_file(dest_encrypted_path)

        return CreatedEncryptedArchive(
            result=True,
            encrypted_key_b64=encrypted_key_b64,
            encrypted_key_nonce=nonce_b64,
            path_encrypted_acc=dest_encrypted_path,
            checksum=checksum
        )

    except Exception as e:
        logger.exception(f"Ошибка при шифровании: {e}")
        return CreatedEncryptedArchive(result=False)


# --- безопасная архивирующая функция (не блокирует loop) ---
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


# --- Синхронная теле-очистка, вызывается в thread (не в event loop) ---
def _sync_cleanup_used_data(
    archive_path: Optional[str],
    base_dir: Optional[str],
    invalid_dir: Optional[str],
    duplicate_dir: Optional[str],
    invalid_archive: Optional[str],
    duplicate_archive: Optional[str],
    item_dirs: List[Optional[str]],
):
    """
    Синхронно удаляет файлы/папки. Вызывать через asyncio.to_thread.
    """
    def _rm_path(p: Optional[str]):
        if not p:
            return
        try:
            pth = Path(p)
            if pth.exists():
                if pth.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    # файл
                    try:
                        os.remove(p)
                    except PermissionError:
                        # на всякий случай: попытка через unlink
                        try:
                            pth.unlink(missing_ok=True)
                        except Exception:
                            pass
        except Exception:
            # здесь логировать нельзя — это sync helper, вызывающий из to_thread,
            # но можно печатать в stderr или просто пропустить
            pass

    # удаляем входной распакованный base_dir (если есть)
    _rm_path(base_dir)

    # удаляем исходный архив-файл (если это требуется)
    _rm_path(archive_path)

    # удаляем папки invalid/duplicate
    _rm_path(invalid_dir)
    _rm_path(duplicate_dir)

    # удаляем zip-файлы архивов (если они есть)
    _rm_path(invalid_archive)
    _rm_path(duplicate_archive)

    # удаляем все item.dir_path (каждый может быть None или уже удалён)
    for d in item_dirs:
        _rm_path(d)


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
