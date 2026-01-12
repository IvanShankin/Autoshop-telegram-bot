from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import send_message
from src.config import get_config
from src.exceptions import AccountCategoryNotFound, \
    TheCategoryStorageAccount
from src.modules.admin_actions.keyboards import to_services_kb, back_in_category_kb
from src.modules.admin_actions.schemas import GetDataForCategoryData
from src.modules.admin_actions.services import safe_get_category
from src.modules.admin_actions.services import set_state_create_category, name_input_prompt_by_language
from src.modules.admin_actions.state import GetDataForCategory
from src.services.database.product_categories.actions import add_category, \
    add_translation_in_category
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data.startswith("add_main_acc_category:"))
async def add_main_acc_category(callback: CallbackQuery, state: FSMContext, user: Users):
    service_id = int(callback.data.split(':')[1])
    await set_state_create_category(state, user, parent_id=None, service_id=service_id)


@router.callback_query(F.data.startswith("add_acc_category:"))
async def add_acc_category(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(category_id, user=user, callback=callback)
    if not category:
        return

    await set_state_create_category(state, user, parent_id=category_id, service_id=category.account_service_id)


@router.message(GetDataForCategory.category_name)
async def add_acc_category_name(message: Message, state: FSMContext, user: Users):
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
        await name_input_prompt_by_language(user, data.service_id, next_lang)
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
        message = get_text(user.language, "admins_editor_category", "Category successfully created!")
        reply_markup = back_in_category_kb(user.language, category.category_id, i18n_key="In category")
    except AccountCategoryNotFound:
        message = get_text(user.language, "admins_editor_category","The category no longer exists")
        reply_markup = to_services_kb(user.language)
    except TheCategoryStorageAccount:
        message = get_text(user.language, "admins_editor_category", "The category stores accounts, please extract them first")
        if data.parent_id:
            reply_markup = back_in_category_kb(user.language, data.parent_id)
        else:
            reply_markup = to_services_kb(user.language)

    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )