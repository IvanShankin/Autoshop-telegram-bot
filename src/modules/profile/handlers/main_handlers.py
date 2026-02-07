from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot_actions.messages import send_message, edit_message
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.profile.keyboards import profile_kb
from src.modules.profile.services.profile_message import get_main_message_profile
from src.services.database.users.models import Users

router_with_repl_kb = Router()
router = Router()


async def handler_profile(
        user: Users,
        send_new_message: bool = True,
        chat_id: int = None,
        message_id: int = None
):
    text = await get_main_message_profile(user, user.language)
    if send_new_message:
        await send_message(
            chat_id=user.user_id,
            message=text,
            image_key="profile",
            reply_markup=profile_kb(user.language, user.user_id)
        )
    else:
        await edit_message(
            chat_id=chat_id,
            message_id=message_id,
            message=text,
            image_key='profile',
            reply_markup=profile_kb(user.language, user.user_id)
        )


@router_with_repl_kb.message(I18nKeyFilter("profile"))
async def handle_profile_message(message: Message, state: FSMContext, user: Users):
    await state.clear()
    await handler_profile(user=user)


@router.callback_query(F.data == "profile")
async def handle_profile_callback(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await handler_profile(
        user=user,
        send_new_message=False,
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id
    )
