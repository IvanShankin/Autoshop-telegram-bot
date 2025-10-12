from src.bot_actions.bot_instance import get_bot_logger
from src.config import MAIN_ADMIN
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply

from src.bot_actions.bot_instance import get_bot
from src.services.system.actions import get_ui_image
from src.services.system.actions import get_settings
from src.utils.core_logger import logger

async def send_message(
        chat_id: int,
        message: str,
        image_key: str = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None
):
    """
    Отправит сообщение по-указанному chat_id, если есть image_key, то отправит фото с сообщением.

    В обоих случаях parse_mode="HTML"
    """
    bot = await get_bot()
    if image_key:
        ui_image = await get_ui_image(image_key)
        if ui_image and ui_image.show: # если есть изображение по данному пути и его можно показывать
            try:
                await bot.send_photo(chat_id, photo=open(ui_image.file_path, "rb"), caption=message, parse_mode="HTML", reply_markup=reply_markup)
            except Exception as e:
                logger.exception(f"#Ошибка при отправке сообщения c фото. Ошибка: {str(e)}")
            return
    try:
        await bot.send_message(chat_id, text=message, parse_mode="HTML", reply_markup=reply_markup)
    except Exception as e:
        logger.exception(f"#Ошибка при отправке сообщения. Ошибка: {str(e)}")

async def send_log(text: str, channel_for_logging_id: int = None):
    """
    :param text: Длинна должна быть в пределах 1 - 4096 символов
    :param channel_for_logging_id: если не передавать то возьмёт сам из настроек
    """

    # формируем сообщения разбивая по максимальной длине (4096)
    parts = []
    for i in range(0, len(text), 4096):
        parts.append(text[i:i + 4096])


    if not channel_for_logging_id:
        settings = await get_settings()
        channel_for_logging_id = settings.channel_for_logging_id

    bot = await get_bot_logger()

    try:
        for message in parts:
            await bot.send_message(channel_for_logging_id, message)
    except Exception as e:
        settings = await get_settings()
        message_error = f"Не удалось отправить сообщение в канал с логами. \n\nОшибка: {str(e)}"
        logger.error(message_error)

        try:
            if settings.support_username:
                await bot.send_message(
                    settings.support_username,
                    f'Не удалось отправить лог в канал!\nID используемого канала: {channel_for_logging_id} '
                    f'\n\nСообщение:'
                )
                for message in parts:
                    await bot.send_message(settings.support_username,message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения support. Ошибка: {str(e)}")

        try:
            await bot.send_message(
                MAIN_ADMIN,
                f'Не удалось отправить лог в канал!\nID используемого канала: {channel_for_logging_id} '
                f'\n\nСообщение:\n{message_error}'
            )
            for message in parts:
                await bot.send_message(MAIN_ADMIN, message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения MAIN_ADMIN. Ошибка: {str(e)}")
