from src.bot_instance import bot
from src.config import MAIN_ADMIN
from src.database.action_core_models import get_settings
from src.utils.core_logger import logger


async def send_log(text: str, channel_for_logging_id: int = None):
    if len(text) > 4096 or len(text) < 1:
        raise ValueError("Длинна текста должна быть в пределлах 1-4096 символов ")

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
            await bot.send_message(settings.support_username,message_error)
            await bot.send_message(MAIN_ADMIN,message_error)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения admin или support. Ошибка: {str(e)}")


