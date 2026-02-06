from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import send_message
from src.config import get_config
from src.exceptions import AccountCategoryNotFound, \
    TheCategoryStorageAccount
from src.modules.admin_actions.keyboards import back_in_category_kb, in_category_editor_kb
from src.modules.admin_actions.schemas import GetDataForCategoryData
from src.modules.admin_actions.services import safe_get_category, set_state_create_category, name_input_prompt_by_language
from src.modules.admin_actions.state import GetDataForCategory
from src.services.database.categories.actions import add_category, add_translation_in_category
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data.startswith("add_category:"))
async def add_category_handler(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = safe_int_conversion(callback.data.split(':')[1])

    if category_id: # если передали значение, значит это подкатегория, иначе это будет главная (is_main)
        category = await safe_get_category(category_id, user=user, callback=callback)
        if not category:
            return

    await set_state_create_category(state, user, parent_id=category_id)


@router.message(GetDataForCategory.category_name)
async def add_category_name(message: Message, state: FSMContext, user: Users):
    # добавление нового перевода
    data = GetDataForCategoryData(**(await state.get_data()))
    data.data_name.update({data.requested_language: message.text})

    # поиск недостающего перевода
    next_lang = None
    for lang_cod in get_config().app.allowed_langs:
        if lang_cod not in data.data_name:
            next_lang = lang_cod

    await state.update_data(
        requested_language=next_lang,
        data_name=data.data_name,
    )

    # если найден недостающий язык -> просим ввести по нему
    if next_lang:
        await name_input_prompt_by_language(user, next_lang)
        await state.set_state(GetDataForCategory.category_name)
        return

    # если заполнили имена -> создаём категорию
    try:
        category = await add_category(
            language=get_config().app.default_lang,
            name=data.data_name[get_config().app.default_lang],
            parent_id=data.parent_id
        )

        for lang_code in data.data_name:
            if lang_code == get_config().app.default_lang:
                continue

            await add_translation_in_category(
                category_id=category.category_id,
                language=lang_code,
                name=data.data_name[lang_code]
            )
        message = get_text(user.language, "admins_editor_category", "category_successfully_created")
        reply_markup = back_in_category_kb(user.language, category.category_id, i18n_key="in_category")
    except AccountCategoryNotFound:
        message = get_text(user.language, "admins_editor_category","category_not_exists")
        reply_markup = in_category_editor_kb(user.language)
    except TheCategoryStorageAccount:
        message = get_text(user.language, "admins_editor_category", "extract_accounts_stored_in_category")
        if data.parent_id:
            reply_markup = back_in_category_kb(user.language, data.parent_id)
        else:
            reply_markup = in_category_editor_kb(user.language)

    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )