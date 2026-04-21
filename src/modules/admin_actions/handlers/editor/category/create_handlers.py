from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.exceptions import AccountCategoryNotFound, TheCategoryStorageAccount
from src.models.create_models.category import CreateCategory, CreateCategoryTranslate
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import back_in_category_kb, in_category_editor_kb
from src.modules.admin_actions.keyboards.editors.category_kb import in_category_kb
from src.modules.admin_actions.schemas import GetDataForCategoryData
from src.modules.admin_actions.services import safe_get_category, set_state_create_category, name_input_prompt_by_language
from src.modules.admin_actions.state import GetDataForCategory
from src.utils.converter import safe_int_conversion
from src.infrastructure.translations import get_text

router = Router()


@router.callback_query(F.data.startswith("add_category:"))
async def add_category_handler(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule,
):
    category_id = safe_int_conversion(callback.data.split(':')[1])

    if category_id: # если передали значение, значит это подкатегория, иначе это будет главная (is_main)
        category = await safe_get_category(
            category_id, user=user, callback=callback, messages_service=messages_service, admin_module=admin_module
        )
        if not category:
            return

    await set_state_create_category(
        state, user, parent_id=category_id, messages_service=messages_service, admin_module=admin_module
    )


@router.message(GetDataForCategory.category_name)
async def add_category_name(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule,
):
    # добавление нового перевода
    data = GetDataForCategoryData(**(await state.get_data()))
    data.data_name.update({data.requested_language: message.text})

    # поиск недостающего перевода
    next_lang = None
    for lang_cod in admin_module.conf.app.allowed_langs:
        if lang_cod not in data.data_name:
            next_lang = lang_cod

    await state.update_data(
        requested_language=next_lang,
        data_name=data.data_name,
    )

    # если найден недостающий язык -> просим ввести по нему
    if next_lang:
        await name_input_prompt_by_language(
            user, next_lang, messages_service=messages_service, admin_module=admin_module
        )
        await state.set_state(GetDataForCategory.category_name)
        return

    # если заполнили имена -> создаём категорию
    try:
        category = await admin_module.category_service.create_category(
            data=CreateCategory(
                language=admin_module.conf.app.default_lang,
                name=data.data_name[admin_module.conf.app.default_lang],
                parent_id=data.parent_id
            )
        )

        for lang_code in data.data_name:
            if lang_code == admin_module.conf.app.default_lang:
                continue

            await admin_module.translations_category_service.create_translation_in_category(
                data=CreateCategoryTranslate(
                    category_id=category.category_id,
                    language=lang_code,
                    name=data.data_name[lang_code]
                ),
                make_commit=True,
                filling_redis=True,
            )
        message = get_text(user.language, "admins_editor_category", "category_successfully_created")
        reply_markup = in_category_kb(user.language, category.category_id)

    except AccountCategoryNotFound:
        message = get_text(user.language, "admins_editor_category","category_not_exists")
        reply_markup = in_category_editor_kb(user.language)
    except TheCategoryStorageAccount:
        message = get_text(user.language, "admins_editor_category", "extract_accounts_stored_in_category")
        if data.parent_id:
            reply_markup = back_in_category_kb(user.language, data.parent_id)
        else:
            reply_markup = in_category_editor_kb(user.language)

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )