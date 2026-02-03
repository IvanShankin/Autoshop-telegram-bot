from aiogram.types import ReactionTypeEmoji

from src.bot_actions.bot_instance import get_bot
from src.utils.core_logger import get_logger


async def like_with_heart(chat_id: int, message_id: int):
    bot = await get_bot()
    try:
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji="❤️")],
            is_big=True  # ВАЖНО: включает фонтан
        )
    except Exception as e:
        get_logger(__name__).warning(f"[like_with_heart] - ошибка при установки реакции: {str(e)}")
