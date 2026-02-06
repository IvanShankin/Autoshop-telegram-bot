from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.exceptions import AccountCategoryNotFound, \
    TheCategoryStorageAccount, CategoryStoresSubcategories
from src.modules.admin_actions.handlers.editor.category.show_handlers import show_category
from src.modules.admin_actions.keyboards import delete_category_kb, back_in_category_kb, \
    delete_product_kb, in_category_editor_kb
from src.modules.admin_actions.services import safe_get_category, upload_category
from src.services.database.categories.actions import delete_category as delete_category_service, \
    delete_product_accounts_by_category
from src.services.database.categories.actions.products.universal.action_delete import \
    delete_product_universal_by_category
from src.services.database.categories.models import ProductType
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()



@router.callback_query(F.data.startswith("category_confirm_delete:"))
async def category_confirm_delete(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])

    await edit_message(
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
async def delete_category(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    reply_markup = None

    try:
        await delete_category_service(category_id)
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

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("confirm_del_all_products:"))
async def confirm_del_all_products(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    await edit_message(
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
async def delete_all_products(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(category_id, user=user, callback=None)
    if not category:
        return

    await upload_category(category, user, callback)
    if category.product_type == ProductType.ACCOUNT:
        await delete_product_accounts_by_category(category_id)
    if category.product_type == ProductType.UNIVERSAL:
        await delete_product_universal_by_category(category_id)

    await callback.answer(get_text(
            user.language,
            "admins_editor_category",
            "products_successfully_deleted"
        ),
        show_alert=True
    )
    await show_category(user, category_id, send_new_message=True)
