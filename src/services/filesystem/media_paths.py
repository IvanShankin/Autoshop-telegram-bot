from pathlib import Path

from src.config import get_config
from src.services.database.categories.models import AccountServiceType, StorageStatus


def create_path_account(
    status: StorageStatus,
    type_account_service: AccountServiceType,
    uuid: str,
    return_path_obj: bool = False
) -> str | Path:
    """
    Создаст путь к аккаунту.

    type_account_service брать с get_config().app.type_account_services (config)

    :return: Полный путь. Пример: .../accounts/for_sale/telegram/gbgbfd-dnnjcs/account.enc
    """
    path = Path(get_config().paths.accounts_dir) / Path(status.value) / Path(type_account_service.value) / Path(uuid) / Path('account.enc')
    return path if return_path_obj else str(path)


def create_path_universal_storage(status: StorageStatus, uuid: str, return_path_obj: bool = False) -> str | Path:
    """
        Создаст путь к универсальному файлу.
        :param return_path_obj: Вернёт экземпляр объекта Path
        :return: Полный путь. Пример: .../universal/for_sale/gbgbfd-dnnjcs/file.enc
    """
    path = Path(get_config().paths.universals_dir) / Path(status.value) / Path(uuid) / "file.enc"
    return path if return_path_obj else str(path)


def create_path_ui_image(file_name: str, return_path_obj: bool = True) -> Path | str:
    """
        Создаст путь к изображению.
        :param return_path_obj: Вернёт экземпляр объекта Path
        :return: Полный путь. Пример: .../ui_sections/example.png
    """
    path = Path(get_config().paths.ui_sections_dir) / Path(file_name)
    return path if return_path_obj else str(path)
