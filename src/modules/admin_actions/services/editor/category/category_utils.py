from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import back_in_category_update_data_kb
from src.modules.admin_actions.keyboards.editors.category_kb import back_in_category_editor_kb
from src.modules.admin_actions.state import GetDataForCategory
from src.utils.i18n import get_text


async def name_input_prompt_by_language(
    user: UsersDTO,
    lang_code: str,
    admin_module: AdminModule,
    messages_service: Messages,
):
    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "set_category_name"
        ).format(language=f'{admin_module.conf.app.emoji_langs[lang_code]} {admin_module.conf.app.name_langs[lang_code]}'),
        reply_markup=back_in_category_editor_kb(user.language)
    )


async def set_state_create_category(
    state: FSMContext,
    user: UsersDTO,
    parent_id: int | None,
    admin_module: AdminModule,
    messages_service: Messages,
):
    await state.clear()
    lang_code = admin_module.conf.app.default_lang

    await state.update_data(
        parent_id=parent_id,
        requested_language=admin_module.conf.app.default_lang,
        data_name={},
        data_description={},
    )

    await name_input_prompt_by_language(user, lang_code, admin_module, messages_service)
    await state.set_state(GetDataForCategory.category_name)


async def update_message_query_data(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    i18n_key: str,
    set_state: State,
    messages_service: Messages,
):
    category_id = int(callback.data.split(':')[1])

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor_category",i18n_key),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )

    await state.update_data(category_id=category_id)
    await state.set_state(set_state)
