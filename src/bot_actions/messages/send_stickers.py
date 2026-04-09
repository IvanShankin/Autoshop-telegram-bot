from src.bot_actions.bot_instance import get_bot
from src.bot_actions.messages.send_log import send_log
from src.exceptions.domain import StickerNotFound
from src.application._database.system.actions.actions import get_sticker
from src.utils.core_logger import get_logger


async def send_sticker(chat_id: int, sticker_key: str):
    """
    :except StickerNotFound: Если не найден
    """
    bot = get_bot()
    sticker = await get_sticker(sticker_key)

    if not sticker:
        raise StickerNotFound()

    if not sticker.show or not sticker.file_id:
        return

    try:
        await bot.send_sticker(
            chat_id=chat_id,
            sticker=sticker.file_id
        )
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception("Ошибка при отправки стикера.\n")
        await send_log(f"Ошибка при отправки стикера: \n{str(e)}")