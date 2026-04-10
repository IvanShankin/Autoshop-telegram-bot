from src.config.env_conf import EnvSettings
from src.config.base import init_env
from src.config.paths_conf import PathSettings



class RuntimeConfig:
    """Все необходимые конфиги для получения секретных данных и работы с сервером хранящий секреты"""

    def __init__(self):
        init_env()
        self.env = EnvSettings.from_env()
        self.paths = PathSettings.build(self.env.use_secret_storage)