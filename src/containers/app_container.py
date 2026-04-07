from src.config import init_config
from src.containers import RequestContainer
from src.infrastructure.crypto_bot.core import init_crypto_provider
from src.infrastructure.rabbit_mq.consumer import RabbitMQConsumer
from src.infrastructure.redis import init_redis, close_redis
from src.infrastructure.telegram.bot_instance import get_bot_logger, get_bot
from src.infrastructure.telegram.client import TelegramClient
from src.services.secrets import init_crypto_context
from src.utils.core_logger import setup_logging


class AppContainer:

    def __init__(self):
        self.conf = init_config()
        self.redis = init_redis()
        self.crypto_provider = init_crypto_provider(self.conf.secrets.token_crypto_bot)

        try:
            self.crypto_context = init_crypto_context()  # необходим config
        except RuntimeError as e:  # если уже есть
            pass

        self.logger = setup_logging(self.conf.paths.log_file)

        self.bot = get_bot()
        self.logger_bot = get_bot_logger()

        self.telegram_client = TelegramClient(bot=self.bot)
        self.telegram_logger_client = TelegramClient(bot=self.logger_bot)

        self.consumer = RabbitMQConsumer(self.handle_event, conf=self.conf, logger=self.logger)


    async def shutdown(self):
        await self.consumer.stop()
        await close_redis()

    def get_request_container(self, session_db) -> RequestContainer:
        return RequestContainer(
            session_db,
            self.telegram_client,
            self.telegram_logger_client,
            self.crypto_provider,
        )

    def _create_event_handler(self, session):
        container = self.get_request_container(session)
        return container.get_event_handler()

    async def handle_event(self, event: dict):
        async_session_factory = self.conf.db_connection.session_local

        async with async_session_factory() as session:
            handler = self._create_event_handler(session)
            await handler.handle(event)