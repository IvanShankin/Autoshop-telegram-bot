import csv
import io
import os.path
import shutil
import zipfile
from pathlib import Path

from src.config import get_config
from src.services.filesystem.actions import get_default_image_bytes
from src.services.products.universals.shemas import get_import_universal_headers


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
    zip_path = conf.paths.example_zip_for_universal_import
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
