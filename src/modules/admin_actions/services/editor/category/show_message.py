from aiogram.types import CallbackQuery

from src.modules.admin_actions.keyboards.editors.category_kb import show_main_categories_kb
from src.bot_actions.messages import edit_message, send_message
from src.modules.admin_actions.keyboards import show_category_admin_kb, change_category_data_kb
from src.modules.admin_actions.services import safe_get_category
from src.services.database.system.actions import get_ui_image
from src.services.database.users.models import Users
from src.utils.i18n import get_text

async def edit_message_in_main_category_editor(user: Users, callback: CallbackQuery):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "Category Editor \n\n"
                "This is where the main categories are located, which the user sees when they navigate to the 'Categories' section"
        ),
        image_key="admin_panel",
        reply_markup=await show_main_categories_kb(user.language)
    )


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
        "admins_editor_category",
        "Category \n\nName: {name}\nIndex: {index}\nShow: {show} \n\nStores items: {is_storage}"
    ).format(name=category.name, index=category.index, show=category.show,is_storage=category.is_product_storage)

    if category.is_product_storage:
        price_one = category.price if category.price else 0
        cost_price = category.cost_price if category.cost_price else 0

        total_sum = category.quantity_product * price_one
        total_cost_price = category.quantity_product * cost_price

        message += get_text(
            user.language,
            "admins_editor_category",
            "\n\nNumber of items in stock: {total_quantity}\n"
            "Sum of all items in stock: {total_sum}\n"
            "Cost of all items in stock: {total_cost_price}\n"
            "Expected profit: {total_profit}"
        ).format(
            total_quantity=category.quantity_product,
            total_sum_acc=total_sum,
            total_cost_price=total_cost_price,
            total_profit=total_sum - total_cost_price,
        )

    reply_markup = await show_category_admin_kb(
        language=user.language,
        current_show=category.show,
        current_index=category.index,
        category_id=category_id,
        parent_category_id=category.parent_id if category.parent_id else None,
        is_main=category.is_main,
        is_product_storage=category.is_product_storage,
        allow_multiple_purchase=category.allow_multiple_purchase,
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
    if not category:
        return

    ui_image = await get_ui_image(category.ui_image_key)
    message = get_text(
        user.language,
        "admins_editor_category",
        "Name: {name} \nDescription: {description} \n\n"
    ).format(name=category.name, description=category.description)

    if category.is_product_storage:
        message += get_text(
            user.language,
            "admins_editor_category",
            "Price of one product: {price} \nCost of one product: {cost_price}\n\n"
        ).format(price=category.price, cost_price=category.cost_price)

    message += get_text(
        user.language,
        "admins_editor_category",
        "Number of buttons per row: {number_button_in_row}\n\n"
        "👇 Select the item to edit"
    ).format(number_button_in_row=category.number_buttons_in_row)

    reply_markup = change_category_data_kb(
        user.language,
        category_id=category_id,
        is_account_storage=category.is_product_storage,
        show_default=False if (ui_image and ui_image.show) else True
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
