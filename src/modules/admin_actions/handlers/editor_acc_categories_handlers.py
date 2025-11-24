import asyncio
import io
import os
from pathlib import Path
from typing import Optional, List, Any, AsyncGenerator

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message, FSInputFile, Document, BufferedInputFile

from src.bot_actions.actions import edit_message, send_message, send_log
from src.bot_actions.bot_instance import get_bot
from src.config import ALLOWED_LANGS, EMOJI_LANGS, NAME_LANGS, DEFAULT_LANG, SUPPORTED_ARCHIVE_EXTENSIONS, \
    TEMP_FILE_DIR, MAX_SIZE_MB, MAX_SIZE_BYTES, MAX_DOWNLOAD_SIZE
from src.exceptions.service_exceptions import AccountCategoryNotFound, \
    TheCategoryStorageAccount, CategoryStoresSubcategories, IncorrectedAmountSale, IncorrectedCostPrice, \
    IncorrectedNumberButton, TypeAccountServiceNotFound, InvalidFormatRows
from src.modules.admin_actions.keyboard_admin import to_services_kb, back_in_service_kb, show_account_category_admin_kb, \
    delete_category_kb, back_in_category_kb, change_category_data_kb, select_lang_category_kb, name_or_description_kb, \
    back_in_category_update_data_kb
from src.modules.admin_actions.schemas.editor_categories import GetDataForCategoryData, UpdateNameForCategoryData, \
    UpdateDescriptionForCategoryData, UpdateCategoryOnlyId, ImportAccountsData
from src.modules.admin_actions.state.editor_categories import GetDataForCategory, UpdateNameForCategory, \
    UpdateDescriptionForCategory, UpdateCategoryImage, UpdateNumberInCategory, ImportTgAccounts, ImportOtherAccounts
from src.services.accounts.other.input_account import input_other_account
from src.services.database.selling_accounts.actions import add_account_category, \
    add_translation_in_account_category, get_account_categories_by_category_id, update_account_category, \
    update_account_category_translation, get_account_service, get_type_account_service
from src.services.database.selling_accounts.actions.actions_delete import delete_account_category
from src.services.database.selling_accounts.models import AccountCategoryFull
from src.services.database.system.actions import get_ui_image, update_ui_image
from src.services.database.users.models import Users
from src.services.accounts.tg.input_account import import_telegram_accounts_from_archive
from src.utils.converter import safe_int_conversion
from src.utils.core_logger import logger
from src.utils.i18n import get_text

router = Router()


async def safe_get_category(category_id: int, user: Users, callback: CallbackQuery | None = None) -> AccountCategoryFull | None:
    """Проверит наличие категории, если нет, то удалит сообщение (если имеется callback) и отошлёт соответствующие сообщение"""
    category = await get_account_categories_by_category_id(
        account_category_id=category_id,
        language=user.language,
        return_not_show=True
    )
    if not category:
        if callback:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.answer(get_text(user.language, 'admins', "The category no longer exists"), show_alert=True)
            return

        await send_message(chat_id=user.user_id,
                           message=get_text(user.language, 'admins', "The category no longer exists"))
        return
    return category


async def show_category(
        user: Users,
        category_id: int,
        send_new_message: bool = False,
        message_id: int = None,
        callback: CallbackQuery = None
):
    category = await safe_get_category(category_id=category_id, user=user, callback=callback)
    if not category:
        return

    message = get_text(
        user.language,
        'admins',
        "Category \n\nName: {name}\nIndex: {index}\nShow: {show} \n\nStores accounts: {is_account_storage}"
    ).format(name=category.name, index=category.index, show=category.show, is_account_storage=category.is_accounts_storage)
    if category.is_accounts_storage:
        price_one_acc = category.price_one_account  if category.price_one_account else 0
        cost_price_acc = category.cost_price_one_account  if category.cost_price_one_account else 0

        total_sum_acc = category.quantity_product_account * price_one_acc
        total_cost_price_acc = category.quantity_product_account * cost_price_acc

        message += get_text(
            user.language,
            'admins',
            "\n\nNumber of stored accounts: {total_quantity_acc}\n"
            "Sum of all stored accounts: {total_sum_acc}\n"
            "Cost of all stored accounts: {total_cost_price_acc}\n"
            "Expected profit: {total_profit}"
        ).format(
            total_quantity_acc=category.quantity_product_account,
            total_sum_acc=total_sum_acc,
            total_cost_price_acc=total_cost_price_acc,
            total_profit=total_sum_acc - total_cost_price_acc,
        )


    reply_markup = await show_account_category_admin_kb(
        language=user.language,
        current_show=category.show,
        current_index=category.index,
        service_id=category.account_service_id,
        category_id=category_id,
        parent_category_id=category.parent_id if category.parent_id else None,
        is_main=category.is_main,
        is_account_storage=category.is_accounts_storage,
    )

    if send_new_message:
        await send_message(
            chat_id=user.user_id,
            message=message,
            reply_markup=reply_markup,
            image_key='admin_panel',
        )
        return
    await edit_message(
        chat_id=user.user_id,
        message_id=message_id,
        message=message,
        reply_markup=reply_markup,
        image_key='admin_panel',
    )


async def show_category_update_data(
        user: Users,
        category_id: int,
        send_new_message: bool = False,
        callback: CallbackQuery = None
):
    category = await safe_get_category(category_id=category_id, user=user, callback=callback)
    ui_image = await get_ui_image(category.ui_image_key)
    if not category:
        return

    message = get_text(
        user.language,
        'admins',
        "Name: {name} \nDescription: {description} \n\n"
    ).format(name=category.name,description=category.description)

    if category.is_accounts_storage:
        message += get_text(
            user.language,
            'admins',
            "Price per account: {account_price} \nCost per account: {cost_price}\n\n"
        ).format(account_price=category.price_one_account, cost_price=category.cost_price_one_account)

    message += get_text(
        user.language,
        'admins',
        "Number of buttons per row: {number_button_in_row}\n\n"
        "👇 Select the item to edit"
    ).format(number_button_in_row=category.number_buttons_in_row)


    reply_markup = change_category_data_kb(
        user.language,
        category_id=category_id,
        is_account_storage=category.is_accounts_storage,
        show_default = False if (ui_image and ui_image.show) else True
    )

    if send_new_message:
        await send_message(
            chat_id=user.user_id,
            message=message,
            reply_markup=reply_markup,
            image_key=category.ui_image_key,
            fallback_image_key='default_catalog_account'
        )
        return

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=reply_markup,
        image_key=category.ui_image_key,
        fallback_image_key='default_catalog_account'
    )


async def name_input_prompt_by_language(user: Users, service_id: int, lang_code: str):
    await send_message(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins",
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
        message=get_text(user.language, 'admins',i18n_key),
        reply_markup=back_in_category_update_data_kb(user.language, category_id)
    )
    await state.update_data(category_id=category_id)
    await state.set_state(set_state)

async def update_data(message: Message, state: FSMContext, user: Users):
    """Обновляет цену за один аккаунт, себестоимость одного аккаунта, число кнопок в строке (только одно)"""
    data = UpdateCategoryOnlyId(**(await state.get_data()))
    new_number = safe_int_conversion(message.text)
    message_error = None

    try:
        await message.delete()
    except Exception:
        pass

    if new_number is None:
        message_error = get_text(user.language, 'miscellaneous', "Incorrect value entered")
    else:
        try:
            if await state.get_state() == UpdateNumberInCategory.price.state:
                await update_account_category(data.category_id, price_one_account=new_number)
            elif await state.get_state() == UpdateNumberInCategory.cost_price.state:
                await update_account_category(data.category_id, cost_price_one_account=new_number)
            elif await state.get_state() == UpdateNumberInCategory.number_button.state:
                await update_account_category(data.category_id, number_buttons_in_row=new_number)
        except (IncorrectedAmountSale, IncorrectedCostPrice, IncorrectedNumberButton):
            message_error = get_text(user.language, 'miscellaneous', "Incorrect value entered")

    if message_error:
        message_error += '\n\n'
        message_error += get_text(user.language, 'miscellaneous', "Try again")
        await send_message(chat_id=user.user_id, message=message_error)
        if await state.get_state() == UpdateNumberInCategory.price.state:
            await state.set_state(UpdateNumberInCategory.price)
        elif await state.get_state() == UpdateNumberInCategory.cost_price.state:
            await state.set_state(UpdateNumberInCategory.cost_price)
        elif await state.get_state() == UpdateNumberInCategory.number_button.state:
            await state.set_state(UpdateNumberInCategory.number_button)
        return

    await show_category_update_data(user, data.category_id, send_new_message=True)
    message_info = await send_message(
        chat_id=user.user_id,
        message=get_text(user.language, 'miscellaneous',"Data updated successfully")
    )

    await asyncio.sleep(3)
    try:
        await message_info.delete()
    except Exception:
        pass


async def service_not_found(user: Users, message_id_delete: Optional[int] = None):
    if message_id_delete:
        try:
            bot = await get_bot()
            await bot.delete_message(user.user_id, message_id_delete)
        except Exception:
            pass

    await send_message(
        chat_id=user.user_id,
        message=get_text(user.language, "admins", "This service no longer exists, please choose another one"),
        reply_markup=to_services_kb(language=user.language)
    )


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
    for lang_cod in ALLOWED_LANGS:
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
        category = await add_account_category(
            account_service_id=data.service_id,
            language=DEFAULT_LANG,
            name=data.data_name[DEFAULT_LANG],
            parent_id=data.parent_id
        )

        for lang_code in data.data_name:
            if lang_code == DEFAULT_LANG:
                continue

            await add_translation_in_account_category(
                account_category_id=category.account_category_id,
                language=lang_code,
                name=data.data_name[lang_code]
            )
        message = get_text(user.language, 'admins', "Category successfully created!")
        reply_markup = back_in_category_kb(user.language, category.account_category_id, i18n_key="In category")
    except AccountCategoryNotFound:
        message = get_text(user.language, 'admins',"The category no longer exists")
        reply_markup = to_services_kb(user.language)
    except TheCategoryStorageAccount:
        message = get_text(user.language, 'admins', "The category stores accounts, please extract them first")
        if data.parent_id:
            reply_markup = back_in_category_kb(user.language, data.parent_id)
        else:
            reply_markup = to_services_kb(user.language)

    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("show_acc_category_admin:"))
async def show_acc_category_admin(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    category_id = int(callback.data.split(':')[1])
    await show_category(user=user, category_id=category_id, message_id=callback.message.message_id, callback=callback)


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


@router.callback_query(F.data.startswith("acc_category_confirm_delete:"))
async def acc_category_confirm_delete(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins",
            "Are you sure you want to delete this category? \n\n"
            "⚠️ Before deleting, make sure this category doesn't contain any subcategories or store accounts!"
        ),
        reply_markup=delete_category_kb(user.language, category_id)
    )


@router.callback_query(F.data.startswith("delete_acc_category:"))
async def delete_acc_category(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    reply_markup = None

    try:
        await delete_account_category(category_id)
        message = get_text(user.language, 'admins',"Category successfully removed!")
        reply_markup = to_services_kb(user.language)
    except AccountCategoryNotFound:
        message = get_text(user.language, 'admins',"The category no longer exists")
    except TheCategoryStorageAccount:
        message = get_text(user.language, 'admins',"The category stores accounts, please extract them first")
    except CategoryStoresSubcategories:
        message = get_text(user.language, 'admins',"The category stores subcategories, delete them first")

    # если попали в except
    if not reply_markup:
        reply_markup = back_in_category_kb(user.language, category_id)

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=reply_markup
    )



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


@router.callback_query(F.data.startswith("choice_lang_category_data:"))
async def choice_lang_category_data(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    lang = callback.data.split(':')[2]

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            'admins',
            "Select the desired section"
        ),
        reply_markup=name_or_description_kb(user.language, category_id, lang)
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
async def acc_category_update_price(message: Message, state: FSMContext, user: Users):
    await update_data(message, state, user)


@router.message(UpdateNumberInCategory.number_button)
async def acc_category_update_price(message: Message, state: FSMContext, user: Users):
    await update_data(message, state, user)



async def check_valid_file(doc: Document, user: Users, state: FSMContext, expected_formats: List[str], set_state: State):
    """Проверит файл на валидный формат и на необходимый размер,
    если один из этих условий не будет выполнено,
    то отошлёт соответствующие сообщение, установит состояние 'set_state' и вернёт False"""
    file_name = doc.file_name
    extension = file_name.split('.')[-1].lower()  # пример: "zip"
    if extension not in expected_formats:
        await send_message(
            user.user_id,
            get_text(
                user.language,
                "admins",
                "This file format is not supported, please send a file with one of these extensions: {extensions_list}"
            ).format(extensions_list=".csv")
        )
        await state.set_state(set_state)
        return False

    if doc.file_size > MAX_DOWNLOAD_SIZE:
        await send_message(
            user.user_id,
            get_text(
                user.language,
                "admins",
                "The file is too large. The maximum size is {max_size_file} MB. \n\nPlease send a different file"
            ).format(extensions_list=MAX_DOWNLOAD_SIZE)
        )
        await state.set_state(set_state)
        return False

    return True


async def message_info_load_file(user: Users) -> AsyncGenerator[Message, None]:
    """Первый вызов: сообщение о скачивание файла. Второй вызов: сообщение об обработке файла"""
    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins",
            "Please wait for the accounts to load and don't touch anything!"
        )
    )
    message_info = await send_message(
        user.user_id,
        get_text(user.language, "admins", "The file is uploaded to the server")
    )

    yield message_info

    await edit_message(
        user.user_id,
        message_info.message_id,
        get_text(
            user.language,
            "admins",
            "The file has been successfully uploaded. The accounts are currently being checked for validity and integrated into the bot"
        )
    )

    yield message_info


async def check_category_is_acc_storage(category: AccountCategoryFull, user: Users) -> bool:
    """
    Проверит что категория - хранилище аккаунтов. Еслине хранит, то отправит сообщение, что необходимо сделать хранилищем
    :return bool: True если хранит, иначе False
    """
    if not category.is_accounts_storage:
        await send_message(
            user.user_id,
            get_text(user.language,"admins","First, make this category an account storage"),
            reply_markup=back_in_category_kb(
                language=user.language,
                category_id=category.category_id,
                i18n_key = "In category"
            )
        )
        return False
    return True


def make_result_msg(
        user: Users,
        successfully_added: int,
        total_processed: int,
        mark_invalid_acc:  Any,
        mark_duplicate_acc: Any,
        tg_acc: bool = False
) -> str:
    result_message = get_text(
        user.language,
        "admins",
        "Account integration was successful. \n\nSuccessfully added: {successfully_added} \nTotal processed: {total_processed}"
    ).format(successfully_added=successfully_added, total_processed=total_processed)
    if mark_invalid_acc:
        result_message += get_text(
            user.language,
            "admins",
            "\n\nWe couldn't extract the account from some {acc_from}(either the structure is broken or the account is invalid); "
            "they were downloaded as a separate file"
        ).format(
            acc_from=  get_text(
                user.language,
                "admins",
                "files" if tg_acc else "lines"
            )
        )
    if mark_duplicate_acc:
        result_message += get_text(
            user.language,
            "admins",
            "\n\nSome accounts are already in the bot; they were downloaded as a separate file"
        )
    return result_message


@router.callback_query(F.data.startswith("acc_category_load_acc:"))
async def acc_category_load_acc(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(category_id, user=user, callback=None)
    if not category:
        return

    service_name = None
    service = await get_account_service(category.account_service_id, return_not_show=True)
    if service:
        type_service = await get_type_account_service(service.type_account_service_id)
        if type_service:
            service_name = type_service.name

    if not service_name:
        await service_not_found(user, callback.message.message_id)

    if service_name == "telegram":
        await edit_message(
            chat_id=user.user_id,
            message_id=callback.message.message_id,
            message=get_text(
                user.language,
                'admins',
                "Send the archive with the exact folder and archive structure as shown in the photo"
            ),
            image_key="info_add_accounts",
            reply_markup=back_in_category_kb(user.language, category_id)
        )
        await state.set_state(ImportTgAccounts.archive)
        await state.update_data(category_id=category_id, type_account_service=service_name)
    elif service_name ==  "other":
        await edit_message(
            chat_id=user.user_id,
            message_id=callback.message.message_id,
            message=get_text(
                user.language,
                'admins',
                "Send a file with the '.csv' extension.\n\n"
                "It must have the structure shown in the photo.\n"
                "Please pay attention to the headers; they must be strictly followed!\n\n"
                "Required Headers (can be copied):\n'<code>phone</code>', '<code>login</code>', '<code>password</code>'\n\n"
                "Note: To create a '.csv' file, create an exal workbook and save it as '.csv'"
            ),
            image_key="example_csv",
            reply_markup=back_in_category_kb(user.language, category_id)
        )
        await state.set_state(ImportOtherAccounts.csv_file)
        await state.update_data(category_id=category_id, type_account_service=service_name)
    else:
        await service_not_found(user, callback.message.message_id)


@router.message(ImportTgAccounts.archive, F.document)
async def import_tg_account(message: Message, state: FSMContext, user: Users):
    async def load_file(file_path: str, caption: str):
        try:
            message_loading = await send_message(
                message.from_user.id, get_text(user.language, "admins", "File loading")
            )
            bot = await get_bot()
            file = FSInputFile(file_path)
            await bot.send_document(message.from_user.id, document=file, caption=caption)
            await message_loading.delete()
        except Exception as e:
            logger.warning(f"[import_tg_account.load_file] - ошибка: '{str(e)}'")
            pass


    data = ImportAccountsData(**(await state.get_data()))
    category = await safe_get_category(data.category_id, user=user, callback=None)
    if not category:
        return

    await check_category_is_acc_storage(category, user)

    doc = message.document
    valid_file = await check_valid_file(
        doc=doc,
        user=user,
        state=state,
        expected_formats=SUPPORTED_ARCHIVE_EXTENSIONS,
        set_state=ImportTgAccounts.archive
    )
    if not valid_file:
        return


    save_path = str(Path(TEMP_FILE_DIR) / doc.file_name)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file = await message.bot.get_file(doc.file_id) # Получаем объект файла

    gen_mes_info = message_info_load_file(user)
    await gen_mes_info.__anext__()
    await message.bot.download_file(file.file_path, destination=save_path) # Скачиваем файл на диск
    message_info = await gen_mes_info.__anext__()

    try:
        gen_import_acc = import_telegram_accounts_from_archive(
            archive_path=save_path,
            account_category_id=data.category_id,
            type_account_service=data.type_account_service
        )
        result = await gen_import_acc.__anext__()

        result_message = make_result_msg(
            user=user,
            successfully_added=result.successfully_added,
            total_processed=result.total_processed,
            mark_invalid_acc=result.invalid_archive_path,
            mark_duplicate_acc=result.duplicate_archive_path,
            tg_acc=True
        )

        await edit_message(
            message.from_user.id,
            message_info.message_id,
            result_message,
            reply_markup=back_in_category_kb(user.language, data.category_id, i18n_key="In category")
        )

        if result.invalid_archive_path:
            await load_file(
                result.invalid_archive_path,
                caption=get_text(user.language,"admins", "Failed account extraction")
            )

        if result.duplicate_archive_path:
            await load_file(
                result.duplicate_archive_path,
                caption=get_text(user.language, "admins", "Duplicate accounts")
            )

    except TypeAccountServiceNotFound:
        await service_not_found(user)
    except Exception as e:
        text = f"#Ошибка_при_добавлении_аккаунтов  [import_tg_account]. \nОшибка='{str(e)}'"
        logger.exception(text)
        await send_log(text)
        await send_message(
            message.from_user.id,
            get_text(user.language,"admins", "An error occurred inside the server, see the logs!")
        )


@router.message(ImportOtherAccounts.csv_file, F.document)
async def import_other_account(message: Message, state: FSMContext, user: Users):
    data = ImportAccountsData(**(await state.get_data()))
    category = await safe_get_category(data.category_id, user=user, callback=None)
    if not category:
        return

    await check_category_is_acc_storage(category, user)

    doc = message.document
    valid_file = await check_valid_file(
        doc=doc,
        user=user,
        state=state,
        expected_formats=["csv"],
        set_state=ImportOtherAccounts.csv_file
    )
    if not valid_file:
        return


    gen_mes_info = message_info_load_file(user)
    await gen_mes_info.__anext__()

    file = await message.bot.get_file(doc.file_id)
    stream = io.BytesIO()
    await message.bot.download_file(file.file_path, stream)
    stream.seek(0)

    message_info = await gen_mes_info.__anext__()

    try:
        result = await input_other_account(stream, data.category_id, data.type_account_service)
        result_message = make_result_msg(
            user=user,
            successfully_added=result.successfully_added,
            total_processed=result.total_processed,
            mark_invalid_acc=result.errors_csv_bytes,
            mark_duplicate_acc=result.duplicates_csv_bytes
        )
        await edit_message(
            message.from_user.id,
            message_info.message_id,
            result_message,
            reply_markup=back_in_category_kb(user.language, data.category_id, i18n_key="In category")
        )
        if result.errors_csv_bytes:
            await message.answer_document(
                BufferedInputFile(
                    result.errors_csv_bytes,
                    filename=get_text(user.language,"admins", "Failed account extraction") + '.csv'
                )
            )
        if result.duplicates_csv_bytes:
            await message.answer_document(
                BufferedInputFile(
                    result.duplicates_csv_bytes,
                    filename=get_text(user.language, "admins", "Duplicate accounts") + '.csv'
                )
            )

    except InvalidFormatRows:
        await edit_message(
            chat_id=user.user_id,
            message_id=message_info.message_id,
            message=get_text(
                user.language,
                'admins',
                "The resulting file has incorrect header formatting. \n"
            "Carefully examine the attached photo and try again \n\n"
            "Required Headers (can be copied):\n'<code>phone</code>', '<code>login</code>', '<code>password</code>'"
            ),
            image_key="example_csv",
            reply_markup=back_in_category_kb(user.language, data.category_id, i18n_key="In category")
        )
        await state.set_state(ImportOtherAccounts.csv_file)
    except TypeAccountServiceNotFound:
        await service_not_found(user)
    except Exception as e:
        text = f"#Ошибка_при_добавлении_аккаунтов  [import_other_account]. \nОшибка='{str(e)}'"
        logger.exception(text)
        await send_log(text)
        await send_message(
            message.from_user.id,
            get_text(user.language,"admins", "An error occurred inside the server, see the logs!")
        )