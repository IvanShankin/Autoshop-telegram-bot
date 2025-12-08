from aiogram.types import CallbackQuery

from src.bot_actions.messages import send_message
from src.services.database.system.actions.actions import get_type_payment
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def safe_get_type_payment(type_payment_id: int, user: Users, callback: CallbackQuery = None):
    type_payment = await get_type_payment(type_payment_id)
    if not type_payment:
        if callback:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.answer(
                get_text(user.language, "admins_editor_replenishments", "There is no longer a payment method"),
                show_alert=True
            )
            return

        await send_message(
            chat_id=user.user_id,
            message=get_text(user.language, "admins_editor_replenishments", "There is no longer a payment method"
        ))
        return
    return type_payment

