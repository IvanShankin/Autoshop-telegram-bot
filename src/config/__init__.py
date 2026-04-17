from asyncio import Semaphore
from typing import Optional, Callable

from src.config.base import init_env
from src.config.db_conf import DbConnectionSettings
from src.config.env_conf import EnvSettings, Mode
from src.config.app_conf import AppConfig
from src.config.file_keys_conf import FileKeysConf, FilePathAndKey
from src.config.message_event_conf import MessageEventConf
from src.config.miscellaneous_conf import MiscellaneousConf
from src.config.paths_conf import PathSettings
from src.config.redis_conf import RedisTimeStorage
from src.config.secrets_conf import load_secrets
from src.config.sizes_conf import FileLimits
from src.infrastructure.telegram.rate_limit import RateLimiter


class RuntimeConfig:
    """Все необходимые конфиги для получения секретных данных и работы с сервером хранящий секреты"""

    def __init__(self):
        init_env()
        self.env = EnvSettings.from_env()
        self.paths = PathSettings.build(self.env.use_secret_storage)


class Config:
    def __init__(self, get_secret: Callable[[str], str]):
        init_env()

        self.env = EnvSettings.from_env()
        self.app = AppConfig()
        self.different = MiscellaneousConf()
        self.message_event = MessageEventConf.build()
        self.paths = PathSettings.build(self.env.use_secret_storage)
        self.redis_time_storage = RedisTimeStorage.build()

        self.secrets = load_secrets(get_secret)
        self.limits = FileLimits()
        self.db_connection = DbConnectionSettings.create(
            db_user=self.env.db_user,
            db_password=self.secrets.db_password,
            db_host=self.env.db_host,
            db_name=self.env.db_name
        )
        self.file_keys = FileKeysConf(
            example_zip_for_universal_import_key=FilePathAndKey(
                key="example_zip_for_universal_import",
                path=self.paths.files_dir / "example_zip_for_universal_import.zip",
                name_in_dir_with_files="example_zip_for_universal_import.zip"
            ),
            example_zip_for_import_tg_acc_key = FilePathAndKey(
                key="example_zip_for_import_tg_acc",
                path=self.paths.files_dir / "example_zip_for_import_tg_acc.zip",
                name_in_dir_with_files="example_zip_for_import_tg_acc.zip"
            ),
            example_csv_for_import_other_acc_key = FilePathAndKey(
                key="example_csv_for_import_other_acc",
                path=self.paths.files_dir / "example_csv_for_import_other_acc.csv",
                name_in_dir_with_files="example_csv_for_import_other_acc.csv"
            )
        )



_config: Optional[Config] = None


def init_config(get_secret: Callable[[str], str]) -> Config:
    global _config
    _config = Config(get_secret)
    return _config


def set_config(config: Config):
    global _config
    _config = config


def get_config() -> Config:
    global _config
    if _config is None:
        raise RuntimeError()
    return _config
