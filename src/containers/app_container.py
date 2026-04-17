from typing import Callable, AsyncGenerator

import aiohttp

from src.application.crypto.crypto_context import CryptoProvider, InitCryptoContext
from src.application.crypto.secrets_storage import GetSecret
from src.config import init_config
from src.config import RuntimeConfig
from src.containers import RequestContainer, init_request_container
from src.infrastructure.crypto.key_store import KeyStore
from src.infrastructure.crypto.secret_storage.client import SecretsStorageClient
from src.infrastructure.crypto.secret_storage.http_secrets_storage import HttpSecretsStorage
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage
from src.infrastructure.crypto_bot.core import init_crypto_bot_provider
from src.infrastructure.rabbit_mq.consumer import RabbitMQConsumer
from src.infrastructure.redis import init_redis, close_redis
from src.infrastructure.telegram.account_client import TelegramAccountClient
from src.infrastructure.telegram.bot_instance import init_bot, init_bot_logger, init_dispatcher
from src.infrastructure.telegram.bot_client import TelegramClient
from src.infrastructure.telegram.ui.keyboard import support_kb
from src.utils.core_logger import setup_logging


class AppContainer:

    def __init__(self):

        runtime_conf = RuntimeConfig()
        secret_client = SecretsStorageClient(
            base_url=runtime_conf.env.storage_server_url,
            cert=(
                str(runtime_conf.paths.ssl_client_cert_file),
                str(runtime_conf.paths.ssl_client_key_file),
            ),
            ca=runtime_conf.paths.ssl_ca_file,
        )
        self.secret_storage: SecretsStorage = HttpSecretsStorage(secret_client) # используется адаптер
        self.logger = setup_logging(runtime_conf.paths.log_file)
        self.crypto_provider = CryptoProvider()

        init_crypto_context = InitCryptoContext(
            storage=self.secret_storage,
            keystore=KeyStore(),
            logger=self.logger,
            runtime_conf=runtime_conf
        )
        self._crypto_context = init_crypto_context.execute()
        self.crypto_provider.set(self._crypto_context)  # ИСПОЛЬЗОВАТЬ ТОЛЬКО ЕГО ДЛЯ ШИФРОВАНИЯ И ДЕШИФРОВАНИЯ

        get_secret = GetSecret(
            storage=self.secret_storage,
            crypto_provider=self.crypto_provider,
            logger=self.logger,
            runtime_conf=runtime_conf
        )

        self.conf = init_config(get_secret.execute)
        self.redis = init_redis(self.conf)
        self.crypto_bot_provider = init_crypto_bot_provider(self.conf.secrets.token_crypto_bot)

        self.bot = init_bot(self.conf)
        self.bot_logger = init_bot_logger(self.conf)

        self.dp_bot = init_dispatcher()
        self.dp_bot_logger = init_dispatcher()

        self.telegram_bot_client = TelegramClient(bot=self.bot)
        self.telegram_bot_logger_client = TelegramClient(bot=self.bot_logger)
        self.telegram_account_client = TelegramAccountClient(self.logger)

        self.consumer = RabbitMQConsumer(self.handle_event, conf=self.conf, logger=self.logger)

        self.http_session = aiohttp.ClientSession()


    async def shutdown(self):
        await self.consumer.stop()
        await close_redis(self.redis)

        if self.http_session:
            await self.http_session.close()


    def get_request_container(self, session_db) -> RequestContainer:
        return init_request_container(
            session_db=session_db,
            session_redis=self.redis,
            config=self.conf,
            http_session=self.http_session,
            telegram_client=self.telegram_bot_client,
            telegram_logger_client=self.telegram_bot_logger_client,
            crypto_bot_provider=self.crypto_bot_provider,
            crypto_provider=self.crypto_provider,
            secret_storage=self.secret_storage,
            support_kb_builder=support_kb,
            telegram_account_client=self.telegram_account_client
        )

    def get_request_container_factory(self) -> Callable[[], AsyncGenerator[RequestContainer, None]]:
        async_session_factory = self.conf.db_connection.session_local

        async def factory() -> AsyncGenerator[RequestContainer, None]:
            async with async_session_factory() as session_db:
                yield self.get_request_container(session_db)

        return factory

    def _create_event_handler(self, session):
        container = self.get_request_container(session)
        return container.get_event_handler()

    async def handle_event(self, event: dict):
        async_session_factory = self.conf.db_connection.session_local

        async with async_session_factory() as session:
            handler = self._create_event_handler(session)
            await handler.handle(event)