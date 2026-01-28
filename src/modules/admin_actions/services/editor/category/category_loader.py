from typing import Optional

from aiogram.types import CallbackQuery

from src.bot_actions.messages import send_message
from src.bot_actions.bot_instance import get_bot
from src.modules.admin_actions.keyboards import in_category_editor_kb
from src.services.database.categories.actions import get_category_by_category_id
from src.services.database.categories.models import CategoryFull
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def safe_get_category(category_id: int, user: Users, callback: CallbackQuery | None = None) -> CategoryFull | None:
    """Проверит наличие категории, если нет, то удалит сообщение (если имеется callback) и отошлёт соответствующие сообщение"""
    category = await get_category_by_category_id(
        category_id=category_id,
        language=user.language,
        return_not_show=True
    )
    if not category:
        if callback:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.answer(get_text(user.language, "admins_editor_category", "The category no longer exists"), show_alert=True)
            return

        await send_message(chat_id=user.user_id,
                           message=get_text(user.language, "admins_editor_category", "The category no longer exists"))
        return
    return category


async def service_not_found(user: Users, message_id_delete: Optional[int] = None):
    if message_id_delete:
        try:
            bot = await get_bot()
            await bot.delete_message(user.user_id, message_id_delete)
        except Exception:
            pass

    await send_message(
        chat_id=user.user_id,
        message=get_text(user.language, "admins_editor_category", "This services no longer exists, please choose another one"),
        reply_markup=in_category_editor_kb(language=user.language)
    )
