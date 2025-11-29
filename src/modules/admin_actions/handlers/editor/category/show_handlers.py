from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message, send_message
from src.modules.admin_actions.keyboards import show_account_category_admin_kb, change_category_data_kb
from src.modules.admin_actions.services.editor.category_loader import safe_get_category
from src.services.database.system.actions import get_ui_image
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()


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
        "admins_editor",
        "Category \n\nName: {name}\nIndex: {index}\nShow: {show} \n\nStores accounts: {is_account_storage}"
    ).format(name=category.name, index=category.index, show=category.show, is_account_storage=category.is_accounts_storage)
    if category.is_accounts_storage:
        price_one_acc = category.price_one_account  if category.price_one_account else 0
        cost_price_acc = category.cost_price_one_account  if category.cost_price_one_account else 0

        total_sum_acc = category.quantity_product_account * price_one_acc
        total_cost_price_acc = category.quantity_product_account * cost_price_acc

        message += get_text(
            user.language,
            "admins_editor",
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
        "admins_editor",
        "Name: {name} \nDescription: {description} \n\n"
    ).format(name=category.name,description=category.description)

    if category.is_accounts_storage:
        message += get_text(
            user.language,
            "admins_editor",
            "Price per account: {account_price} \nCost per account: {cost_price}\n\n"
        ).format(account_price=category.price_one_account, cost_price=category.cost_price_one_account)

    message += get_text(
        user.language,
        "admins_editor",
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


@router.callback_query(F.data.startswith("show_acc_category_admin:"))
async def show_acc_category_admin(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    category_id = int(callback.data.split(':')[1])
    await show_category(user=user, category_id=category_id, message_id=callback.message.message_id, callback=callback)

