from src.config import get_config
from src.infrastructure.redis import get_redis
from src.utils.core_logger import get_logger


class Container:
    """
    Контейнер для сборки сервисного слоя. Вызывается строго только в middleware!
    """

    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.session_redis = get_redis()





def init_container() -> Container:
    return Container()


