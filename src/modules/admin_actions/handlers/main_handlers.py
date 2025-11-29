from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot_actions.messages import send_message, edit_message
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.admin_actions.keyboards import main_admin_kb
from src.services.database.admins.actions import check_admin
from src.services.database.users.models import Users

router_with_repl_kb = Router()
router = Router()

async def handler_admin(
    user: Users,
    send_new_message: bool = True,
    message_id: int = None
):
    if send_new_message:
        await send_message(
            chat_id=user.user_id,
            image_key="admin_panel",
            reply_markup=main_admin_kb(user.language)
        )
    else:
        await edit_message(
            chat_id=user.user_id,
            message_id=message_id,
            image_key="admin_panel",
            reply_markup=main_admin_kb(user.language)
        )


@router_with_repl_kb.message(I18nKeyFilter("Admin panel"))
async def handle_profile_message(message: Message, state: FSMContext, user: Users):
    if not await check_admin(message.from_user.id):
        return
    await state.clear()
    if await check_admin(message.from_user.id):
        await handler_admin(user=user)


@router.callback_query(F.data == "admin_panel")
async def handle_profile_callback(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await handler_admin(
        user=user,
        send_new_message=False,
        message_id=callback.message.message_id
    )



