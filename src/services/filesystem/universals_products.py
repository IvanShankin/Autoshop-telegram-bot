import csv
import io
import os.path
import shutil
import zipfile
from pathlib import Path
from typing import List

from src.bot_actions.messages import send_log
from src.config import get_config
from src.services.database.categories.models.product_universal import StorageStatus
from src.services.database.categories.models import SoldUniversalFull
from src.services.filesystem.actions import get_default_image_bytes, move_file
from src.services.filesystem.media_paths import create_path_universal_storage
from src.services.products.universals.shemas import get_import_universal_headers, UploadUniversalProduct
from src.utils.core_logger import get_logger


async def move_in_universal(universal: SoldUniversalFull, status: StorageStatus) -> bool:
    """
    Перенос универсального товара к `status` удалив исходное местоположение.
    :param status: статус продукта который будет в конечном пути
    :return: Если возникнет ошибка или аккаунт не переместится, то вернёт False
    """
    orig = None
    final = None
    try:
        orig = create_path_universal_storage(
            status=universal.universal_storage.status,
            uuid=universal.universal_storage.storage_uuid
        )
        final = create_path_universal_storage(
            status=status,
            uuid=universal.universal_storage.storage_uuid
        )

        moved = await move_file(orig, final)
        if not moved:
            return False

        # Удаление директории где хранится товар (uui). Директория уже будет пустой
        if os.path.isdir(str(Path(orig).parent)):
            shutil.rmtree(str(Path(orig).parent))

        return True
    except Exception as e:
        text = (
            f"#Ошибка при переносе универсального товара к {status}. \n"
            f"Исходный путь: {orig if orig else "none"} \n"
            f"Финальный путь: {final if final else "none"} \n"
            f"universal_storage_id: {universal.universal_storage_id if universal.universal_storage_id else "none"} \n"
            f"Ошибка: {str(e)}"
        )
        logger = get_logger(__name__)
        logger.exception(f"Ошибка при переносе универсального товара к {status} %s", universal.universal_storage_id)
        await send_log(text)
        return False


async def generate_example_zip_for_import() -> Path:
    """
    Генерирует пример ZIP-архива для universal import:
    ├── manifest.csv
    └── files/
        ├── file_001.pdf
        ├── file_002.pdf
        └── image_003.png
    """
    conf = get_config()
    zip_path = conf.file_keys.example_zip_for_universal_import_key.path

    if os.path.isfile(zip_path):
        shutil.rmtree(zip_path.parent, ignore_errors=True)

    zip_path.parent.mkdir(parents=True, exist_ok=True)

    headers = get_import_universal_headers()
    allowed_langs = conf.app.allowed_langs

    # CSV content
    csv_buffer = io.StringIO()
    csv_buffer.write("\ufeff") # для корректного определения UTC-8 в Excel

    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=headers,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL
    )
    writer.writeheader()

    writer.writerow({
        "filename": "file_001.pdf",
        **{f"description_{lang}": f"Описание товара 1 ({lang})" for lang in allowed_langs}
    })

    writer.writerow({
        "filename": "file_002.pdf",
        **{f"description_{lang}": f"Описание товара 2 ({lang})" for lang in allowed_langs}
    })

    csv_content = csv_buffer.getvalue()
    csv_buffer.close()

    # ZIP
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # manifest.csv
        zipf.writestr("manifest.csv", csv_content)

        # files/
        zipf.writestr("files/", "")

        # fake pdf files
        zipf.writestr(
            "files/file_001.pdf",
            b"%PDF-1.4\n% Fake PDF file 001\n"
        )
        zipf.writestr(
            "files/file_002.pdf",
            b"%PDF-1.4\n% Fake PDF file 002\n"
        )

        # placeholder image
        image_bytes = get_default_image_bytes()
        zipf.writestr(
            "files/image_003.png",
            image_bytes
        )

    return zip_path


def create_import_zip(
    base_dir: Path,
    zip_path: Path
) -> None:
    """
    Упаковывает manifest.csv и files/ в zip
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for path in base_dir.rglob("*"):
            if path.is_file():
                zipf.write(
                    path,
                    arcname=path.relative_to(base_dir)
                )


def create_manifest_csv(
    csv_path: Path,
    headers: List[str],
    products: List[UploadUniversalProduct]
) -> None:
    """
    Создаёт manifest.csv с товарами
    """
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=headers,
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL
        )
        writer.writeheader()

        for product in products:
            row = {"filename": product.file_name or ""}

            for header in headers:
                if header.startswith("description_"):
                    lang = header.replace("description_", "")
                    row[header] = product.descriptions.get(lang, "")

            writer.writerow(row)