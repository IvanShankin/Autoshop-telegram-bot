from pathlib import Path

from src.config import get_config
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.categories.models.product_universal import UniversalStorageStatus


def create_path_account(status: str, type_account_service: AccountServiceType, uuid: str) -> str:
    """
    Создаст путь к аккаунту.

    type_account_service брать с get_config().app.type_account_services (config)

    :return: Полный путь. Пример: .../accounts/for_sale/telegram/gbgbfd-dnnjcs/account.enc
    """
    return str(Path(get_config().paths.accounts_dir) / status / type_account_service.value / uuid / 'account.enc')


def create_path_universal_storage(status: UniversalStorageStatus, uuid: str, return_path_obj: bool = False) -> str | Path:
    """
        Создаст путь к универсальному файлу.
        :param return_path_obj: Вернёт экземпляр объекта Path
        :return: Полный путь. Пример: .../universal/for_sale/gbgbfd-dnnjcs/file.enc
    """
    path = Path(get_config().paths.universals_dir) / Path(status.value) / Path(uuid) / "file.enc"
    return path if return_path_obj else str(path)