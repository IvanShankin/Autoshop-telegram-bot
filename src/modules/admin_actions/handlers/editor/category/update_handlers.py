import io

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.actions import edit_message, send_message
from src.config import MAX_SIZE_MB, MAX_SIZE_BYTES
from src.exceptions.service_exceptions import AccountCategoryNotFound, \
    TheCategoryStorageAccount, CategoryStoresSubcategories
from src.modules.admin_actions.handlers.editor.category.show_handlers import show_category, show_category_update_data
from src.modules.admin_actions.keyboard_admin import to_services_kb, select_lang_category_kb, \
    back_in_category_update_data_kb
from src.modules.admin_actions.schemas.editor_categories import UpdateNameForCategoryData, \
    UpdateDescriptionForCategoryData, UpdateCategoryOnlyId
from src.modules.admin_actions.services.editor.category_loader import safe_get_category
from src.modules.admin_actions.services.editor.category_updater import update_data
from src.modules.admin_actions.services.editor.category_utils import update_message_query_data
from src.modules.admin_actions.services.editor.upload_accounts import upload_account
from src.modules.admin_actions.state.editor_categories import UpdateNameForCategory, \
    UpdateDescriptionForCategory, UpdateCategoryImage, UpdateNumberInCategory
from src.services.database.selling_accounts.actions import update_account_category, \
    update_account_category_translation
from src.services.database.system.actions import update_ui_image
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data.startswith("acc_category_update_storage:"))
async def acc_category_update_storage(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    is_storage = bool(int(callback.data.split(':')[2])) # что необходимо установить

    try:
        await update_account_category(category_id, is_accounts_storage=is_storage)
        message = get_text(user.language, 'admins', "Successfully updated")
    except AccountCategoryNotFound:
        try:
            await callback.message.delete()
        except Exception:
            pass
        message = get_text(user.language, 'admins', "The category no longer exists")
    except TheCategoryStorageAccount:
        message = get_text(user.language, 'admins', "The category stores accounts, please extract them first")
    except CategoryStoresSubcategories:
        message = get_text(user.language, 'admins',"The category stores subcategories, delete them first")

    await callback.answer(message, show_alert=True)
    await show_category(user=user, category_id=category_id, message_id=callback.message.message_id, callback=callback)


@router.callback_query(F.data.startswith("acc_category_update_index:"))
async def service_update_index(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    new_index = int(callback.data.split(':')[2])

    if new_index >= 0:
        await update_account_category(category_id, index=new_index)
    await callback.answer(get_text(user.language, 'admins',"Successfully updated"))
    await show_category(user=user, category_id=category_id, message_id=callback.message.message_id, callback=callback)


@router.callback_query(F.data.startswith("acc_category_update_show:"))
async def service_update_show(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    show = bool(int(callback.data.split(':')[2]))

    await update_account_category(category_id, show=show)
    await callback.answer(get_text(user.language, 'admins',"Successfully updated"))
    await show_category(user=user, category_id=category_id, message_id=callback.message.message_id, callback=callback)


@router.callback_query(F.data.startswith("category_update_data:"))
async def category_update_data(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    await state.clear()
    await show_category_update_data(user, category_id, callback=callback)


@router.callback_query(F.data.startswith("acc_category_update_name_or_des:"))
async def acc_category_update_name_or_des(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            'admins',
            "Select the language to change"
        ),
        reply_markup=select_lang_category_kb(user.language, category_id)
    )


@router.callback_query(F.data.startswith("acc_category_update_name:"))
async def acc_category_update_name(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    lang = callback.data.split(':')[2]
    category = await safe_get_category(category_id, user=user, callback=callback)
    if not category:
        return

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            'admins',
            "Enter a new name\n\nCurrent name: {name}"
        ).format(name=category.name),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )

    await state.update_data(category_id=category_id, language=lang)
    await state.set_state(UpdateNameForCategory.name)


@router.message(UpdateNameForCategory.name)
async def get_name_for_update(message: Message, state: FSMContext, user: Users):
    data = UpdateNameForCategoryData( **(await state.get_data()))
    try:
        await update_account_category_translation(
            account_category_id=data.category_id,
            language=data.language,
            name=message.text,
        )
        message = get_text(user.language, 'admins', "Name changed successfully")
        reply_markup = back_in_category_update_data_kb(user.language, data.category_id)
    except AccountCategoryNotFound:
        message = get_text(user.language, 'admins',"The category no longer exists")
        reply_markup=to_services_kb(user.language)

    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("acc_category_update_descr:"))
async def acc_category_update_descr(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    lang = callback.data.split(':')[2]
    category = await safe_get_category(category_id, user=user, callback=callback)
    if not category:
        return

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            'admins',
            "Enter a new description \n\nCurrent description: {description}"
        ).format(description=category.description),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )

    await state.update_data(category_id=category_id, language=lang)
    await state.set_state(UpdateDescriptionForCategory.description)


@router.message(UpdateDescriptionForCategory.description)
async def get_description_for_update(message: Message, state: FSMContext, user: Users):
    data = UpdateDescriptionForCategoryData( **(await state.get_data()))
    try:
        await update_account_category_translation(
            account_category_id=data.category_id,
            language=data.language,
            description=message.text,
        )
        message = get_text(user.language, 'admins', "Description changed successfully")
        reply_markup = back_in_category_update_data_kb(user.language, data.category_id)
    except AccountCategoryNotFound:
        message = get_text(user.language, 'admins',"The category no longer exists")
        reply_markup=to_services_kb(user.language)

    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("update_show_ui_default_category:"))
async def update_show_ui_default_category(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    set_show = bool(int(callback.data.split(':')[2]))
    category = await safe_get_category(category_id, user=user, callback=callback)
    if not category:
        return

    await update_ui_image(key=category.ui_image_key, show=set_show)
    await show_category_update_data(user=user, category_id=category_id, callback=callback)


@router.callback_query(F.data.startswith("acc_category_update_image:"))
async def acc_category_update_image(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            'admins',
            "Send a photo. Be sure to include a document for greater image clarity!"
        ),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )
    await state.update_data(category_id=category_id)
    await state.set_state(UpdateCategoryImage.image)


@router.message(UpdateCategoryImage.image, F.document)
async def update_category_image(message: Message, state: FSMContext, user: Users):
    doc = message.document
    data = UpdateCategoryOnlyId(**(await state.get_data()))
    category = await safe_get_category(data.category_id, user=user, callback=None)
    if not category:
        return

    reply_markup = None

    if not doc.mime_type.startswith("image/"): # Проверяем, что это действительно изображение
        text = get_text(user.language,'admins', "This is not an image. Send it as a document")
        reply_markup = back_in_category_update_data_kb(user.language, category.account_category_id)
    elif doc.file_size > MAX_SIZE_BYTES: # Проверяем размер, известный Telegram (без скачивания)
        text = get_text(
            user.language,
            'admins',
            "The file is too large — maximum {max_size_mb} MB. \n\nTry again"
        ).format(max_size_mb=MAX_SIZE_MB)
        reply_markup = back_in_category_update_data_kb(user.language, category.account_category_id)
    else:
        # Получаем объект файла
        file = await message.bot.get_file(doc.file_id)

        # Скачиваем файл в поток
        byte_stream = io.BytesIO()
        await message.bot.download_file(file.file_path, byte_stream)

        # Преобразуем поток  bytes
        file_bytes = byte_stream.getvalue()
        try:
            await update_account_category(data.category_id, file_data=file_bytes)
            text = get_text(user.language, 'admins', "Image installed successfully")
            reply_markup = back_in_category_update_data_kb(user.language, category.account_category_id)
        except AccountCategoryNotFound:
            text = get_text(user.language, 'admins', "The category no longer exists")

    await send_message(
        chat_id=user.user_id,
        message=text,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("acc_category_update_price:"))
async def acc_category_update_price(callback: CallbackQuery, state: FSMContext, user: Users):
    await update_message_query_data(
        callback, state, user,
        i18n_key="Please send an integer - the price per account",
        set_state=UpdateNumberInCategory.price
    )


@router.callback_query(F.data.startswith("acc_category_update_cost_price:"))
async def acc_category_update_cost_price(callback: CallbackQuery, state: FSMContext, user: Users):
    await update_message_query_data(
        callback, state, user,
        i18n_key="Please send an integer - the cost price per account",
        set_state=UpdateNumberInCategory.cost_price
    )


@router.callback_query(F.data.startswith("acc_category_update_number_button:"))
async def acc_category_update_number_button(callback: CallbackQuery, state: FSMContext, user: Users):
    await update_message_query_data(
        callback, state, user,
        i18n_key="Please send an integer - the number of buttons in one line for the category \n\nAllowed: from 1 to 8",
        set_state=UpdateNumberInCategory.number_button
    )


@router.message(UpdateNumberInCategory.price)
async def acc_category_update_price(message: Message, state: FSMContext, user: Users):
    await update_data(message, state, user)


@router.message(UpdateNumberInCategory.cost_price)
async def acc_category_cost_price(message: Message, state: FSMContext, user: Users):
    await update_data(message, state, user)


@router.message(UpdateNumberInCategory.number_button)
async def acc_category_number_button(message: Message, state: FSMContext, user: Users):
    await update_data(message, state, user)


@router.callback_query(F.data.startswith("acc_category_upload_acc:"))
async def acc_category_upload_acc(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(category_id, user=user, callback=None)
    if not category:
        return

    await upload_account(category, user, callback)
