from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import main_admin_kb


router_with_repl_kb = Router()
router = Router()


async def handler_admin(
    user: UsersDTO,
    messages_service: Messages,
    send_new_message: bool = True,
    message_id: int = None,
):
    if send_new_message:
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            event_message_key="admin_panel",
            reply_markup=main_admin_kb(user.language)
        )
    else:
        await messages_service.edit_msg.edit(
            chat_id=user.user_id,
            message_id=message_id,
            event_message_key="admin_panel",
            reply_markup=main_admin_kb(user.language)
        )


@router_with_repl_kb.message(I18nKeyFilter("admin_panel"))
async def handle_profile_message(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages
):
    if not await admin_module.admin_service.check_admin(message.from_user.id):
        return

    await state.clear()
    if await admin_module.admin_service.check_admin(message.from_user.id):
        await handler_admin(user=user, messages_service=messages_service)


@router.callback_query(F.data == "admin_panel")
async def handle_profile_callback(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages
):
    await state.clear()
    await handler_admin(
        user=user,
        messages_service=messages_service,
        send_new_message=False,
        message_id=callback.message.message_id
    )



