from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.models.read_models import UsersDTO
from src.modules.profile.keyboards import profile_kb
from src.modules.profile.services.profile_message import get_main_message_profile
from src.services.bot import Messages
from src.services.models.modules import ProfileModule

router_with_repl_kb = Router()
router = Router()


async def handler_profile(
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
    send_new_message: bool = True,
    chat_id: int = None,
    message_id: int = None,
):
    text = await get_main_message_profile(user, user.language, profile_module)
    if send_new_message:
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=text,
            event_message_key="profile",
            reply_markup=profile_kb(user.language, user.user_id)
        )
    else:
        await messages_service.edit_msg.edit(
            chat_id=chat_id,
            message_id=message_id,
            message=text,
            event_message_key='profile',
            reply_markup=profile_kb(user.language, user.user_id)
        )


@router_with_repl_kb.message(I18nKeyFilter("profile"))
async def handle_profile_message(
    message: Message, state: FSMContext, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    await state.clear()
    await handler_profile(user=user, profile_module=profile_module, messages_service=messages_service)


@router.callback_query(F.data == "profile")
async def handle_profile_callback(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    await state.clear()
    await handler_profile(
        user=user,
        send_new_message=False,
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        profile_module=profile_module,
        messages_service=messages_service,
    )
