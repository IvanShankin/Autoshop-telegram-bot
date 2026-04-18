from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.infrastructure.translations import get_text


async def safe_get_type_payment(
    type_payment_id: int,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    callback: CallbackQuery = None,
):
    type_payment = await admin_module.type_payments_service.get_type_payment(type_payment_id)
    if not type_payment:
        if callback:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.answer(
                get_text(user.language, "admins_editor_replenishments", "payment_method_not_exists"),
                show_alert=True
            )
            return

        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=get_text(user.language, "admins_editor_replenishments", "payment_method_not_exists"
        ))
        return
    return type_payment

