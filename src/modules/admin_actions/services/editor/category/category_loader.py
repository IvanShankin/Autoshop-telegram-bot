from typing import Optional

from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.infrastructure.telegram.bot_client import TelegramClient
from src.modules.admin_actions.keyboards import in_category_editor_kb
from src.models.read_models import CategoryFull, UsersDTO
from src.infrastructure.translations import get_text


async def safe_get_category(
    category_id: int, user: UsersDTO, admin_module: AdminModule, messages_service: Messages, callback: CallbackQuery | None = None,
) -> CategoryFull | None:
    """Проверит наличие категории, если нет, то удалит сообщение (если имеется callback) и отошлёт соответствующие сообщение"""
    category = await admin_module.category_service.get_category_by_id(
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
            await callback.answer(get_text(user.language, "admins_editor_category", "category_not_exists"), show_alert=True)
            return

        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=get_text(user.language, "admins_editor_category", "category_not_exists")
        )
        return
    return category


async def service_not_found(
    user: UsersDTO,
    messages_service: Messages,
    tg_client: TelegramClient,
    message_id_delete: Optional[int] = None,
):
    if message_id_delete:
        try:
            await tg_client.delete_message(user.user_id, message_id_delete)
        except Exception:
            pass

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(user.language, "admins_editor_category", "selected_product_type_not_found"),
        reply_markup=in_category_editor_kb(language=user.language)
    )
