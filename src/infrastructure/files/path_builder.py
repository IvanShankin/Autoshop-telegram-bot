from pathlib import Path

from src.config import Config
from src.database.models.categories import StorageStatus, AccountServiceType


class PathBuilder:

    def __init__(self, conf: Config):
        self.conf = conf

    def build_path_account(
        self,
        status: StorageStatus,
        type_account_service: AccountServiceType,
        uuid: str,
        as_path: bool = False
    ) -> str | Path:
        """
        Создаст путь к аккаунту.

        type_account_service брать с get_config().app.type_account_services (config)

        :return: Полный путь. Пример: .../accounts/for_sale/telegram/gbgbfd-dnnjcs/account.enc
        """
        path = Path(self.conf.paths.accounts_dir) / Path(status.value) / Path(type_account_service.value) / Path(
            uuid) / Path('account.enc')
        return path if as_path else str(path)

    def build_path_universal_storage(
        self,
        status: StorageStatus,
        uuid: str,
        as_path: bool = False
    ) -> str | Path:
        """
            Создаст путь к универсальному файлу.
            :param as_path: Вернёт экземпляр объекта Path
            :return: Полный путь. Пример: .../universal/for_sale/gbgbfd-dnnjcs/file.enc
        """
        path = Path(self.conf.paths.universals_dir) / Path(status.value) / Path(uuid) / "file.enc"
        return path if as_path else str(path)

    def build_path_ui_image(
        self,
        file_name: str,
        as_path: bool = True
    ) -> Path | str:
        """
            Создаст путь к изображению.
            :param as_path: Вернёт экземпляр объекта Path
            :return: Полный путь. Пример: .../ui_sections/example.png
        """
        path = Path(self.conf.paths.ui_sections_dir) / Path(file_name)
        return path if as_path else str(path)

    def build_path_file(
        self,
        file_name: str,
        as_path: bool = True
    ) -> Path | str:
        """
            Создаст путь к изображению.
            :param as_path: Вернёт экземпляр объекта Path
            :return: Полный путь. Пример: .../ui_sections/example.png
        """
        path = Path(self.conf.paths.files_dir) / Path(file_name)
        return path if as_path else str(path)
