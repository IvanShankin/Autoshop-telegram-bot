from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message, send_message
from src.config import get_config
from src.modules.admin_actions.keyboards import back_in_category_update_data_kb
from src.modules.admin_actions.keyboards.editors.category_kb import back_in_category_editor_kb
from src.modules.admin_actions.state import GetDataForCategory
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def name_input_prompt_by_language(user: Users, lang_code: str):
    await send_message(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "Specify the category name for this language: {language}"
        ).format(language=f'{get_config().app.emoji_langs[lang_code]} {get_config().app.name_langs[lang_code]}'),
        reply_markup=back_in_category_editor_kb(user.language)
    )


async def set_state_create_category(
    state: FSMContext,
    user: Users,
    parent_id: int | None
):
    await state.clear()
    lang_code = get_config().app.default_lang

    await state.update_data(
        parent_id=parent_id,
        requested_language=get_config().app.default_lang,
        data_name={},
        data_description={},
    )
    await name_input_prompt_by_language(user, lang_code)
    await state.set_state(GetDataForCategory.category_name)


async def update_message_query_data(
    callback: CallbackQuery,
    state: FSMContext,
    user: Users,
    i18n_key: str,
    set_state: State
):
    category_id = int(callback.data.split(':')[1])
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor_category",i18n_key),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )
    await state.update_data(category_id=category_id)
    await state.set_state(set_state)
