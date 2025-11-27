from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot_actions.actions import edit_message
from src.exceptions.service_exceptions import AccountCategoryNotFound, \
    TheCategoryStorageAccount, CategoryStoresSubcategories
from src.modules.admin_actions.handlers.editor.category.show_handlers import show_category
from src.modules.admin_actions.handlers.editor.keyboard import to_services_kb, delete_category_kb, back_in_category_kb, \
    delete_accounts_kb
from src.modules.admin_actions.services.editor.category_loader import safe_get_category, safe_get_service_name, \
    service_not_found
from src.modules.admin_actions.services.editor.upload_accounts import upload_account
from src.modules.admin_actions.state.editor_categories import ImportTgAccounts, ImportOtherAccounts
from src.services.database.selling_accounts.actions.actions_delete import delete_account_category, \
    delete_product_accounts_by_category
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()



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


@router.callback_query(F.data.startswith("confirm_del_all_acc:"))
async def confirm_del_all_acc(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            'admins',
            "Are you sure you want to permanently delete all accounts currently for sale?"
            "\n\nNote: They will be uploaded to this chat before deletion"
        ),
        reply_markup=delete_accounts_kb(user.language, category_id)
    )


@router.callback_query(F.data.startswith("delete_all_account:"))
async def delete_all_account(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(category_id, user=user, callback=None)
    if not category:
        return

    await upload_account(category, user, callback)
    await delete_product_accounts_by_category(category_id)

    await callback.answer("Accounts successfully deleted", show_alert=True)
    await show_category(user, category_id, send_new_message=True)


@router.callback_query(F.data.startswith("acc_category_load_acc:"))
async def acc_category_load_acc(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(category_id, user=user, callback=None)
    if not category:
        return

    service_name = await safe_get_service_name(category, user, callback.message.message_id)

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

