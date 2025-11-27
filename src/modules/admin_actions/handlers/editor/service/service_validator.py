from aiogram.types import CallbackQuery

from src.bot_actions.actions import edit_message, send_message
from src.modules.admin_actions.handlers.editor.keyboard import show_service_acc_admin_kb
from src.services.database.selling_accounts.actions import get_account_service
from src.services.database.users.models import Users
from src.utils.i18n import  get_text

async def show_service(user: Users, service_id: int, send_new_message: bool = False, message_id: int = None, callback: CallbackQuery = None):
    service = await get_account_service(service_id, return_not_show=True)
    if not service:
        if callback:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.answer(get_text(user.language, "admins_editor","The services is no longer available"), show_alert=True)
            return

        await send_message(chat_id=user.user_id, message=get_text(user.language, "admins_editor","The services is no longer available"))
        return

    message = get_text(
        user.language,
        "admins_editor",
        "Service \n\nName: {name}\nIndex: {index}\nShow: {show}"
    ).format(name=service.name, index=service.index, show=service.show)
    reply_markup = await show_service_acc_admin_kb(
        language=user.language,
        current_show=service.show,
        current_index=service.index,
        service_id=service_id
    )

    if send_new_message:
        await send_message(
            chat_id=user.user_id,
            message=message,
            reply_markup=reply_markup,
            image_key='admin_panel',
        )
        return

    await edit_message(
        chat_id=user.user_id,
        message_id=message_id,
        message=message,
        reply_markup=reply_markup,
        image_key='admin_panel',
    )

