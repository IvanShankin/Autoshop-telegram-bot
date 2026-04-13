import tempfile
from pathlib import Path

from src.application._secrets.crypto_context import get_crypto_context
from src.config import get_config
from src.domain.crypto.encrypt import make_account_key, encrypt_folder
from src.domain.crypto.utils import sha256_file
from src.infrastructure.files.file_system import make_archive, make_csv_bytes
from src.application.products.accounts.other.dto.schemas import REQUIRED_HEADERS
from src.application.products.accounts.tg.dto.schemas import CreatedEncryptedArchive
from src.utils.core_logger import get_logger


TXT_FILES = [
    "example_input_data_1.txt",
    "example_input_data_2.txt",
]


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


def generate_example_import_other_acc() -> None:
    """Создаёт пример CSV-файла для импорта аккаунтов"""

    data = [
        {
            "phone": "+79161234567",
            "login": "ivan.petrov",
            "password": "Qwerty123!",
        },
        {
            "phone": "+79169876543",
            "login": "anna.smirnova",
            "password": "StrongPass#9",
        },
        {
            "phone": "+79005554433",
            "login": "test.user",
            "password": "Test1234",
        },
    ]

    bytes_csv = make_csv_bytes(
        data=data,
        headers=REQUIRED_HEADERS,
        excel_compatible=True,
    )

    conf = get_config()
    path = Path(conf.file_keys.example_csv_for_import_other_acc_key.path)

    path.write_bytes(bytes_csv)


async def generate_example_import_tg_acc() -> bool:
    """
    Создаёт пример ZIP-архива для импорта аккаунтов
    Создаёт архив со структурой:
    ├── archive_1.zip
    ├── archive_2.zip
    └── dir/
        └── tdata/
            ├── example_input_data_1.txt
            └── example_input_data_2.txt
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        #  archive_1
        archive_1_dir = tmp_path / "archive_1" / "tdata"
        archive_1_dir.mkdir(parents=True)

        for name in TXT_FILES:
            (archive_1_dir / name).touch()

        archive_1_zip = tmp_path / "archive_1.zip"
        ok = await make_archive(
            data_for_archiving=str(tmp_path / "archive_1"),
            new_path_archive=str(archive_1_zip),
        )
        if not ok:
            return False

        #  archive_2
        archive_2_dir = tmp_path / "archive_2" / "tdata"
        archive_2_dir.mkdir(parents=True)

        for name in TXT_FILES:
            (archive_2_dir / name).touch()

        archive_2_zip = tmp_path / "archive_2.zip"
        ok = await make_archive(
            data_for_archiving=str(tmp_path / "archive_2"),
            new_path_archive=str(archive_2_zip),
        )
        if not ok:
            return False

        #  dir (НЕ архивируется отдельно)
        dir_tdata = tmp_path / "dir" / "tdata"
        dir_tdata.mkdir(parents=True)

        for name in TXT_FILES:
            (dir_tdata / name).touch()

        conf = get_config()
        #  финальный архив
        ok = await make_archive(
            data_for_archiving=[
                str(archive_1_zip),
                str(archive_2_zip),
                str(tmp_path / "dir"),
            ],
            new_path_archive=conf.file_keys.example_zip_for_import_tg_acc_key.path,
        )
        return ok


