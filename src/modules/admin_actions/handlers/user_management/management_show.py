from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.modules.admin_actions.keyboards import back_in_main_admin_kb
from src.modules.admin_actions.services import message_about_user
from src.modules.admin_actions.state import GetUserIdOrUsername
from src.services.database.users.actions import get_user
from src.services.database.users.actions.action_user import get_user_by_username
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data.startswith("get_id_or_user_user_management"))
async def get_id_or_user_user_management(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.set_state(GetUserIdOrUsername.get_id_or_username)
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "send_user_id_or_username"
        ),
        image_key='admin_panel',
        reply_markup=back_in_main_admin_kb(user.language)
    )


@router.message(GetUserIdOrUsername.get_id_or_username)
async def get_user_id_or_username(message: Message, user: Users, state: FSMContext):
    user_message = message.text
    result_convert_int = safe_int_conversion(user_message)
    target_user = None

    # ищем по id
    if result_convert_int: # если смогли преобразовать в int
        target_user = await get_user(result_convert_int)
    else:
        user_message.replace("@", '') # подгоняем под данные в БД
        users_list = await get_user_by_username(user_message)

        if len(users_list) == 1:
            target_user = users_list[0]
        elif len(users_list) > 1:
            await send_message(
                user.user_id,
                get_text(user.language, "admins_user_mang", "multiple_users_with_same_username"),
                reply_markup=back_in_main_admin_kb(user.language)
            )
            return

    # если нашли
    if target_user:
        await message_about_user(True, admin=user, target_user=target_user)
        await state.clear()
    else:
        await send_message(
            user.user_id,
            get_text(user.language, "admins_user_mang", "user_not_found_by_id_or_username"),
            reply_markup=back_in_main_admin_kb(user.language)
        )


@router.callback_query(F.data.startswith("user_management:"))
async def user_management(callback: CallbackQuery, state: FSMContext, user: Users):
    target_user_id = int(callback.data.split(':')[1])
    target_user = await get_user(target_user_id)
    await message_about_user(False, admin=user, target_user=target_user, message_id=callback.message.message_id)
    await state.clear()


