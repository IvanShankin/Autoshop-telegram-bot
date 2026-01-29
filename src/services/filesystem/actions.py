import asyncio
import os
import shutil
import tempfile
import uuid
import zipfile
from io import BytesIO
from PIL import Image
from pathlib import Path
from typing import Optional, List, AsyncGenerator

from src.config import get_config
from src.utils.core_logger import get_logger



def _sync_create_zip_multiple(paths: list[str], archive_path: str):
    """Синхронное создание ZIP архива"""
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for source_path in paths:
            if os.path.isfile(source_path):
                # Добавляем один файл
                arcname = os.path.basename(source_path)
                zipf.write(source_path, arcname)
            else:
                # Добавляем директорию
                base_dir = os.path.dirname(source_path)
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=base_dir)
                        zipf.write(file_path, arcname)



# Синхронная теле-очистка, вызывается в thread (не в event loop)
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


def check_file_exists(file_path: str) -> bool:
    return True if os.path.exists(file_path) else False


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


async def make_archive(data_for_archiving: str | List[str], new_path_archive: str) -> bool:
    """
    Создает один ZIP архив, содержащий:
      - файл
      - директорию
      - или несколько файлов/директорий (списком)

    :param data_for_archiving: путь или список путей
    :param new_path_archive: путь для создания архива
    :return: bool
    """
    try:
        # Унифицируем вход — приводим к списку
        if isinstance(data_for_archiving, str):
            paths = [data_for_archiving]
        else:
            paths = list(data_for_archiving)

        # Проверяем существование каждого пути
        for p in paths:
            if not os.path.exists(p):
                logger = get_logger(__name__)
                logger.error(f"Ошибка: путь '{p}' не существует")
                return False

        # Создаем директорию для архива
        archive_file = ensure_zip_path(new_path_archive)
        archive_dir = archive_file.parent
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Создаём ZIP в отдельном потоке
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_create_zip_multiple, paths, str(archive_file))

        return True

    except Exception as e:
        logger = get_logger(__name__)
        logger.exception(f"Ошибка make_archive: {e}")
        return False


# helper: передвигает файлы в потоке, возвращает True если всё успешно
def move_file_sync(src: str, dst: str) -> bool:
    """
        Перемещение аккаунтов

        Если путь к src не будет найден, то вернёт False
        :param src: путь к зашифрованному файл.
        :param dst: Путь к новому месту (Директория).
        :return: Bool результат
    """
    try:
        if not os.path.isfile(src) and not os.path.isdir(src) :
            return False
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return True
    except Exception:
        return False


async def move_file(src: str, dst: str) -> bool:
    return await asyncio.to_thread(move_file_sync, src, dst)


def ensure_zip_path(path: str | Path) -> Path:
    """Гарантирует, что путь указывает на файл .zip, а не на директорию."""
    path = Path(path)

    if path.exists() and path.is_dir():
        return path.with_suffix(".zip")

    if path.suffix.lower() != ".zip":
        return path.with_suffix(".zip")

    return path


def get_dir_size(path: str) -> int:
    """
    Возвращает общий размер директории в байтах.
    """
    total = 0
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                total += os.path.getsize(file_path)
            except OSError:
                pass  # например, если файл недоступен
    return total


def copy_file(src: str, dst_dir: str, file_name: str = None) -> str:
    """
    Копирует файл в указанную директорию.
    Создаёт директорию, если её нет.
    Возвращает путь к новому файлу.
    :param file_name: Если необходимо установить имя файла. Передавать с расширением
    """
    if not os.path.isfile(src):
        raise FileNotFoundError(f"Файл не найден: {src}")

    os.makedirs(dst_dir, exist_ok=True)

    # Имя файла сохраняем
    filename = file_name if file_name else os.path.basename(src)
    dst_path = os.path.join(dst_dir, filename)

    shutil.copy2(src, dst_path)

    return dst_path


async def split_file_on_chunk(file_path: str) -> AsyncGenerator[str, None]:
    """
    Поделит файл на части по максимальному допустимому размеру для выгрузки в ТГ
    :return: Путь к части файла
    """
    part = 1

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(get_config().limits.max_download_size)
            if not chunk:
                break

            temp_path = get_config().paths.temp_file_dir / f"log_file_part_{part}.log"
            with open(temp_path, "wb") as out:
                out.write(chunk)

            yield temp_path

            os.remove(temp_path)
            part += 1


def get_default_image_bytes(color: str = "white", size: tuple[int, int] = (500, 500)) -> bytes:
    """
    Создаёт изображение-заглушку и возвращает его в виде байтов (PNG).
    Подходит для передачи в create_ui_image как file_data.
    """
    img = Image.new("RGB", size, color=color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_temp_dir(name: str = None) -> Path:
    conf = get_config()

    temp_dir_path = conf.paths.temp_file_dir / str(name if name else uuid.uuid4())
    os.mkdir(temp_dir_path)

    return temp_dir_path
