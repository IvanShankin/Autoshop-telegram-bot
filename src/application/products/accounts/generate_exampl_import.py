import tempfile
from pathlib import Path

from src.application.products.accounts.other.dto.schemas import REQUIRED_HEADERS
from src.config import Config
from src.infrastructure.files.file_system import make_csv_bytes, make_archive


class GenerateExamplImportAccount:

    def __init__(
        self,
        conf: Config
    ):
        self.conf = conf
        self.TXT_FILES = [
            "example_input_data_1.txt",
            "example_input_data_2.txt",
        ]


    def generate_example_import_other_acc(self,) -> None:
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

        path = Path(self.conf.file_keys.example_csv_for_import_other_acc_key.path)

        path.write_bytes(bytes_csv)

    async def generate_example_import_tg_acc(self, ) -> bool:
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

            for name in self.TXT_FILES:
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

            for name in self.TXT_FILES:
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

            for name in self.TXT_FILES:
                (dir_tdata / name).touch()

            #  финальный архив
            ok = await make_archive(
                data_for_archiving=[
                    str(archive_1_zip),
                    str(archive_2_zip),
                    str(tmp_path / "dir"),
                ],
                new_path_archive=self.conf.file_keys.example_zip_for_import_tg_acc_key.path,
            )
            return ok
