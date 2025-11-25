import asyncio
from typing import Optional, List, Any, AsyncGenerator

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message, Document

from src.bot_actions.actions import edit_message, send_message
from src.bot_actions.bot_instance import get_bot
from src.config import EMOJI_LANGS, NAME_LANGS, DEFAULT_LANG, MAX_DOWNLOAD_SIZE
from src.exceptions.service_exceptions import IncorrectedAmountSale, IncorrectedCostPrice, \
    IncorrectedNumberButton
from src.modules.admin_actions.keyboard_admin import to_services_kb, back_in_service_kb, show_account_category_admin_kb, \
    back_in_category_kb, change_category_data_kb, back_in_category_update_data_kb
from src.modules.admin_actions.schemas.editor_categories import UpdateCategoryOnlyId
from src.modules.admin_actions.state.editor_categories import GetDataForCategory, UpdateNumberInCategory
from src.services.database.selling_accounts.actions import get_account_categories_by_category_id, \
    update_account_category, \
    get_account_service, get_type_account_service
from src.services.database.selling_accounts.models import AccountCategoryFull
from src.services.database.system.actions import get_ui_image
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text


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


async def safe_get_service_name(category: AccountCategoryFull, user: Users, message_id: int) -> str | None:
    """Произведёт поиск по сервисам, если не найдёт, то удалит сообщение и отошлёт соответствующие сообщение"""
    service_name = None
    service = await get_account_service(category.account_service_id, return_not_show=True)
    if service:
        type_service = await get_type_account_service(service.type_account_service_id)
        if type_service:
            return type_service.name

    if not service_name:
        await service_not_found(user, message_id)

    return None


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
