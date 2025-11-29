from typing import Optional

from aiogram.types import CallbackQuery

from src.bot_actions.messages import send_message
from src.bot_actions.bot_instance import get_bot
from src.modules.admin_actions.keyboards import to_services_kb
from src.services.database.selling_accounts.actions import get_account_categories_by_category_id, \
    get_account_service, get_type_account_service
from src.services.database.selling_accounts.models import AccountCategoryFull
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def safe_get_category(category_id: int, user: Users, callback: CallbackQuery | None = None) -> AccountCategoryFull | None:
    """Проверит наличие категории, если нет, то удалит сообщение (если имеется callback) и отошлёт соответствующие сообщение"""
    category = await get_account_categories_by_category_id(
        account_category_id=category_id,
        language=user.language,
        return_not_show=True
    )
    if not category:
        if callback:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.answer(get_text(user.language, "admins_editor", "The category no longer exists"), show_alert=True)
            return

        await send_message(chat_id=user.user_id,
                           message=get_text(user.language, "admins_editor", "The category no longer exists"))
        return
    return category


async def safe_get_service_name(category: AccountCategoryFull, user: Users, message_id: int) -> str | None:
    """Произведёт поиск по сервисам, если не найдёт, то удалит сообщение и отошлёт соответствующие сообщение"""
    service_name = None
    service = await get_account_service(category.account_service_id, return_not_show=True)
    if service:
        type_service = await get_type_account_service(service.type_account_service_id)
        if type_service:
            return type_service.name

    if not service_name:
        await service_not_found(user, message_id)

    return None


async def service_not_found(user: Users, message_id_delete: Optional[int] = None):
    if message_id_delete:
        try:
            bot = await get_bot()
            await bot.delete_message(user.user_id, message_id_delete)
        except Exception:
            pass

    await send_message(
        chat_id=user.user_id,
        message=get_text(user.language, "admins_editor", "This services no longer exists, please choose another one"),
        reply_markup=to_services_kb(language=user.language)
    )
