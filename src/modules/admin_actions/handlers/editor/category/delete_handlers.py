from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.exceptions import AccountCategoryNotFound, TheCategoryStorageAccount, CategoryStoresSubcategories
from src.infrastructure.telegram.bot_client import TelegramClient
from src.models.read_models import UsersDTO
from src.modules.admin_actions.handlers.editor.category.show_handlers import show_category
from src.modules.admin_actions.keyboards import delete_category_kb, back_in_category_kb, \
    delete_product_kb, in_category_editor_kb
from src.modules.admin_actions.services import safe_get_category, upload_category
from src.database.models.categories import ProductType
from src.utils.i18n import get_text

router = Router()



@router.callback_query(F.data.startswith("category_confirm_delete:"))
async def category_confirm_delete(callback: CallbackQuery, user: UsersDTO, messages_service: Messages,):
    category_id = int(callback.data.split(':')[1])

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "question_about_deleting_category"
        ),
        reply_markup=delete_category_kb(user.language, category_id)
    )


@router.callback_query(F.data.startswith("delete_category:"))
async def delete_category(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages, admin_module: AdminModule,
):
    category_id = int(callback.data.split(':')[1])
    reply_markup = None

    try:
        await admin_module.category_service.delete_category(category_id)
        message = get_text(user.language, "admins_editor_category","category_successfully_removed")
        reply_markup = in_category_editor_kb(user.language)
    except AccountCategoryNotFound:
        message = get_text(user.language, "admins_editor_category","category_not_exists")
    except TheCategoryStorageAccount:
        message = get_text(user.language, "admins_editor_category","extract_accounts_stored_in_category")
    except CategoryStoresSubcategories:
        message = get_text(user.language, "admins_editor_category","first_delete_subcategory")

    # если попали в except
    if not reply_markup:
        reply_markup = back_in_category_kb(user.language, category_id)

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("confirm_del_all_products:"))
async def confirm_del_all_products(callback: CallbackQuery, user: UsersDTO, messages_service: Messages,):
    category_id = int(callback.data.split(':')[1])
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "question_about_deleting_all_products_on_sale"
        ),
        reply_markup=delete_product_kb(user.language, category_id)
    )


@router.callback_query(F.data.startswith("delete_all_products:"))
async def delete_all_products(
    callback: CallbackQuery,
    user: UsersDTO,
    messages_service: Messages,
    admin_module: AdminModule,
    tg_client: TelegramClient
):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(
        category_id, user=user, callback=None, messages_service=messages_service, admin_module=admin_module
    )
    if not category:
        return

    await upload_category(
        category,
        user,
        callback,
        messages_service=messages_service,
        admin_module=admin_module,
        tg_client=tg_client
    )
    if category.product_type == ProductType.ACCOUNT:
        await admin_module.account_moduls.product_service.delete_product_accounts_by_category(category_id)
    if category.product_type == ProductType.UNIVERSAL:
        await admin_module.universal_moduls.product_service.delete_product_universal_by_category(category_id)

    await callback.answer(get_text(
            user.language,
            "admins_editor_category",
            "products_successfully_deleted"
        ),
        show_alert=True
    )
    await show_category(
        user, category_id, send_new_message=True, admin_module=admin_module, messages_service=messages_service
    )
