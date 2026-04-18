from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.infrastructure.translations import get_text


async def support_kb(language: str, support_username: str):
    if not support_username:
        return None

    support_name = get_text(language, 'kb_start', "support")

    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(
            text=support_name,
            url=f"https://t.me/{support_username.lstrip('@')}"
        )
    )
    kb.adjust(1)

    return kb.as_markup()