from logging import Logger
from typing import Optional, TYPE_CHECKING

from src.config import Config
from src.infrastructure.telegram.rate_limit import RateLimiter
from src.models.read_models import LogLevel
from src.application.models.systems import SettingsService


if TYPE_CHECKING:
    from src.infrastructure.telegram.bot_client import TelegramClient


class SendLogs:
    def __init__(
        self,
        tg_logger_client: "TelegramClient",
        limiter: RateLimiter,
        settings_service: SettingsService,
        conf: Config,
        logger: Logger,
    ):
        """
        :param limiter: ОБЯЗАТЕЛЬНОГО ГЛОБАЛЬНЫЙ!
        """
        self.tg_logger_client = tg_logger_client
        self.limiter = limiter
        self.settings_service = settings_service
        self.conf = conf
        self.logger = logger

    async def send_log(self, text: str, log_lvl: Optional[LogLevel] = None):
        """
        Отошлёт лог в файл и в канал.
        :param log_lvl: При наличии, запишет в файл с соответствующим уровнем
        """

        if log_lvl:
            if log_lvl == LogLevel.INFO:
                self.logger.info(text)
            if log_lvl == LogLevel.WARNING:
                self.logger.warning(text)
            if log_lvl == LogLevel.ERROR:
                self.logger.error(text)

        # формируем сообщения разбивая по максимальной длине (4096)
        parts = []
        for i in range(0, len(text), 4096):
            parts.append(text[i:i + 4096])

        settings = await self.settings_service.get_settings()
        channel_for_logging_id = settings.channel_for_logging_id

        try:
            for message in parts:
                await self.limiter.acquire()
                await self.tg_logger_client.send_message(int(channel_for_logging_id), message)
        except Exception as e:
            settings = await self.settings_service.get_settings()
            message_error = (
                f"Не удалось отправить сообщение в канал с логами.\n"
                f"ID используемого канала: {channel_for_logging_id} "
                f"\n\nОшибка: {str(e)}"
            )
            self.logger.error(message_error)

            try:
                if settings.support_username:
                    await self.limiter.acquire()
                    await self.tg_logger_client.send_message(settings.support_username, message_error)
                    for message in parts:
                        await self.limiter.acquire()
                        await self.tg_logger_client.send_message(settings.support_username, message)
            except Exception as e:
                self.logger.error(f"Ошибка отправки сообщения support. Ошибка: {str(e)}")

            try:
                await self.limiter.acquire()
                await self.tg_logger_client.send_message(self.conf.env.main_admin, message_error)
                for message in parts:
                    await self.limiter.acquire()
                    await self.tg_logger_client.send_message(self.conf.env.main_admin, message)
            except Exception as e:
                self.logger.error(f"Ошибка отправки сообщения MAIN_ADMIN. Ошибка: {str(e)}")