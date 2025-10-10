from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply

from src.bot_actions.bot_instance import get_bot
from src.services.system.actions import get_ui_image
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
