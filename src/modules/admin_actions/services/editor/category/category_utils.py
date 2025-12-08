from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message, send_message
from src.config import EMOJI_LANGS, NAME_LANGS, DEFAULT_LANG
from src.modules.admin_actions.keyboards import back_in_service_kb, back_in_category_update_data_kb
from src.modules.admin_actions.state import GetDataForCategory
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def name_input_prompt_by_language(user: Users, service_id: int, lang_code: str):
    await send_message(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor",
            "Specify the category name for this language: {language}"
        ).format(language=f'{EMOJI_LANGS[lang_code]} {NAME_LANGS[lang_code]}'),
        reply_markup=back_in_service_kb(user.language, service_id)
    )


async def set_state_create_category(
        state: FSMContext,
        user: Users,
        service_id: int,
        parent_id: int | None
):
    await state.clear()
    lang_code = DEFAULT_LANG

    await state.update_data(
        service_id=service_id,
        parent_id=parent_id,
        requested_language=DEFAULT_LANG,
        data_name={},
        data_description={},
    )
    await name_input_prompt_by_language(user, service_id, lang_code)
    await state.set_state(GetDataForCategory.category_name)


async def update_message_query_data(callback: CallbackQuery, state: FSMContext, user: Users, i18n_key: str, set_state: State):
    category_id = int(callback.data.split(':')[1])
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor",i18n_key),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )
    await state.update_data(category_id=category_id)
    await state.set_state(set_state)
