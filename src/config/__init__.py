import os
from asyncio import Semaphore
from typing import Optional

from src.config.base import init_env
from src.config.db_conf import DbConnectionSettings
from src.config.env_conf import EnvSettings, Mode
from src.config.app_conf import AppConfig
from src.config.miscellaneous_conf import MiscellaneousConf
from src.config.paths_conf import PathSettings
from src.config.secrets_conf import load_secrets
from src.config.sizes_conf import FileLimits
from src.services.secrets.runtime import set_runtime, RuntimeMode, SecretsRuntime
from src.bot_actions.throttler import RateLimiter



class Config:
    def __init__(self):
        init_env()

        self.env = EnvSettings.from_env()
        self.app = AppConfig()
        self.different = MiscellaneousConf()
        self.paths = PathSettings.build()

        # инициализировать необходимо не позже чем устанавливаем секреты (при установке секретов используется runtime)
        set_runtime(
            SecretsRuntime(
                mode=RuntimeMode(self.env.mode),
                storage_url=self.env.storage_server_url,
                cert=(
                    str(self.paths.ssl_client_cert_file),
                    str(self.paths.ssl_client_key_file),
                ),
                ca=str(self.paths.ssl_ca_file),
            )
        )

        self.secrets = load_secrets()
        self.limits = FileLimits()
        self.db_connection = DbConnectionSettings.create(
            db_user=self.env.db_user,
            db_password=self.secrets.db_password,
            db_host=self.env.db_host,
            db_name=self.env.db_name
        )



_config: Optional[Config] = None
_GLOBAL_RATE_LIMITER: Optional[RateLimiter] = None
_SEMAPHORE_MAILING: Optional[Semaphore] = None

def init_config():
    global _config
    _config = Config()


def set_config(config: Config):
    global _config
    _config = config


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def get_global_rate_limit() -> RateLimiter:
    global _GLOBAL_RATE_LIMITER
    if _GLOBAL_RATE_LIMITER is None:
        _GLOBAL_RATE_LIMITER = RateLimiter(max_calls=get_config().different.rate_send_msg_limit, period=1.0)

    return _GLOBAL_RATE_LIMITER


def get_semaphore_mailing() -> Semaphore:
    global _SEMAPHORE_MAILING
    if _SEMAPHORE_MAILING is None:
        _SEMAPHORE_MAILING = Semaphore(get_config().different.semaphore_mailing_limit)

    return _SEMAPHORE_MAILING