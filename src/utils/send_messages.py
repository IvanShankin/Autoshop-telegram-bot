from src.bot_instance import bot
from src.config import MAIN_ADMIN
from src.services.system.actions import get_settings
from src.utils.core_logger import logger


async def send_log(text: str, channel_for_logging_id: int = None):
    """
    :param text: Длинна должна быть в пределах 1 - 4096 символов
    :param channel_for_logging_id: если не передавать то возьмёт сам из настроек
    """
    if len(text) > 4096 or len(text) < 1:
        return

    if not channel_for_logging_id:
        settings = await get_settings()
        channel_for_logging_id = settings.channel_for_logging_id

    try:
        await bot.send_message(channel_for_logging_id, text)
    except Exception as e:
        settings = await get_settings()
        message_error = f"Не удалось отправить сообщение в канал с логами. Ошибка: {str(e)}"
        logger.error(message_error)

        try:
            if settings.support_username:
                await bot.send_message(
                    settings.support_username,
                    f'Не удалось отправить лог в канал!\nID используемого канала: {channel_for_logging_id} '
                    f'\n\nСообщение:\n{message_error}'
                )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения support. Ошибка: {str(e)}")

        try:
            await bot.send_message(
                MAIN_ADMIN,
                f'Не удалось отправить лог в канал!\nID используемого канала: {channel_for_logging_id} '
                f'\n\nСообщение:\n{message_error}'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения MAIN_ADMIN. Ошибка: {str(e)}")
