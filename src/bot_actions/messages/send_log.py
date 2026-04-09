from typing import Optional

from src.bot_actions.bot_instance import get_bot_logger
from src.models.read_models import LogLevel
from src.config import get_config, get_global_rate_limit

from src.application._database.system.actions import get_settings
from src.utils.core_logger import get_logger


async def send_log(text: str, log_lvl: Optional[LogLevel] = None, channel_for_logging_id: Optional[int] = None):
    """
    Отошлёт лог в файл и в канал.
    :param log_lvl: При наличии, запишет в файл с соответствующим уровнем
    :param channel_for_logging_id: если не передавать то возьмёт сам из настроек
    """
    logger = get_logger(__name__)

    if log_lvl:
        if log_lvl == LogLevel.INFO:
            logger.info(text)
        if log_lvl == LogLevel.WARNING:
            logger.warning(text)
        if log_lvl == LogLevel.ERROR:
            logger.error(text)


    # формируем сообщения разбивая по максимальной длине (4096)
    parts = []
    for i in range(0, len(text), 4096):
        parts.append(text[i:i + 4096])


    if not channel_for_logging_id:
        settings = await get_settings()
        channel_for_logging_id = settings.channel_for_logging_id

    bot = get_bot_logger()

    try:
        for message in parts:
            await get_global_rate_limit().acquire()
            await bot.send_message(int(channel_for_logging_id), message)
    except Exception as e:
        logger = get_logger(__name__)

        settings = await get_settings()
        message_error = (
            f"Не удалось отправить сообщение в канал с логами.\n"
            f"ID используемого канала: {channel_for_logging_id} "
            f"\n\nОшибка: {str(e)}"
        )
        logger.error(message_error)

        try:
            if settings.support_username:
                await get_global_rate_limit().acquire()
                await bot.send_message(settings.support_username, message_error)
                for message in parts:
                    await get_global_rate_limit().acquire()
                    await bot.send_message(settings.support_username,message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения support. Ошибка: {str(e)}")

        try:
            await get_global_rate_limit().acquire()
            await bot.send_message(get_config().env.main_admin, message_error)
            for message in parts:
                await get_global_rate_limit().acquire()
                await bot.send_message(get_config().env.main_admin, message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения MAIN_ADMIN. Ошибка: {str(e)}")

