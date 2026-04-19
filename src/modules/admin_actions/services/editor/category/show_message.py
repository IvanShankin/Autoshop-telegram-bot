from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards.editors.category_kb import show_main_categories_kb
from src.modules.admin_actions.keyboards import show_category_admin_kb, change_category_data_kb
from src.modules.admin_actions.services import safe_get_category
from src.database.models.categories import ProductType, AccountServiceType
from src.infrastructure.translations import get_text


async def edit_message_in_main_category_editor(
    user: UsersDTO,
    callback: CallbackQuery,
    messages_service: Messages,
    admin_module: AdminModule,
):
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "main_category_editor"
        ),
        event_message_key="admin_panel",
        reply_markup=await show_main_categories_kb(user.language, admin_module)
    )


async def show_category(
    user: UsersDTO,
    category_id: int,
    admin_module: AdminModule,
    messages_service: Messages,
    send_new_message: bool = False,
    message_id: int = None,
    callback: CallbackQuery = None
):
    category = await safe_get_category(
        category_id=category_id,
        user=user,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )
    if not category:
        return

    message = get_text(
        user.language,
        "admins_editor_category",
        "category_admin_info"
    ).format(
        name=category.name,
        index=category.index,
        show=category.show,
        is_storage=category.is_product_storage,
    )

    if category.product_type == ProductType.UNIVERSAL:
        message += get_text(
            user.language,
            "admins_editor_category",
             "additional_universal_category_info"
        ).format(
            reuse_product=category.reuse_product,
            media_type=get_text(
                user.language,
                "admins_editor_category",
                 str(category.media_type.value)
            )
        )

    if category.is_product_storage:
        storage_type = "None"
        if category.product_type == ProductType.UNIVERSAL:
            storage_type = get_text(user.language, "admins_editor_category", "universal_product")
        if category.product_type == ProductType.ACCOUNT:
            if category.type_account_service == AccountServiceType.TELEGRAM:
                storage_type = get_text(user.language, "admins_editor_category", "tg_accounts")
            elif category.type_account_service == AccountServiceType.OTHER:
                storage_type = get_text(user.language, "admins_editor_category", "other_accounts")

        message += get_text(
            user.language, "admins_editor_category", "type_account_in_category"
        ).format(storage_type=storage_type)

        price_one = category.price if category.price else 0
        cost_price = category.cost_price if category.cost_price else 0

        total_sum = category.quantity_product * price_one
        total_cost_price = category.quantity_product * cost_price

        message += get_text(
            user.language,
            "admins_editor_category",
            "category_admin_data_by_products"
        ).format(
            total_quantity=category.quantity_product,
            total_sum=total_sum,
            total_cost_price=total_cost_price,
            total_profit=total_sum - total_cost_price,
        )

    reply_markup = await show_category_admin_kb(
        language=user.language,
        category_id=category_id,
        category=category,
        admin_module=admin_module,
    )

    if send_new_message:
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=message,
            reply_markup=reply_markup,
            event_message_key='admin_panel',
        )
        return

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=message_id,
        message=message,
        reply_markup=reply_markup,
        event_message_key='admin_panel',
    )


async def show_category_update_data(
    user: UsersDTO,
    category_id: int,
    admin_module: AdminModule,
    messages_service: Messages,
    send_new_message: bool = False,
    callback: CallbackQuery = None,
):
    category = await safe_get_category(
        category_id=category_id,
        user=user,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )
    if not category:
        return

    ui_image = await admin_module.ui_images_service.get_ui_image(category.ui_image_key)
    message = get_text(
        user.language,
        "admins_editor_category",
        "name_and_description_admin_category"
    ).format(name=category.name, description=category.description)

    if category.is_product_storage:
        message += get_text(
            user.language,
            "admins_editor_category",
            "price_in_admin_category"
        ).format(price=category.price, cost_price=category.cost_price)

    message += get_text(
        user.language,
        "admins_editor_category",
        "number_of_buttons_per_row_and_select_paragraph"
    ).format(number_button_in_row=category.number_buttons_in_row)

    reply_markup = change_category_data_kb(
        user.language,
        category_id=category_id,
        is_product_storage=category.is_product_storage,
        show_default=False if (ui_image and ui_image.show) else True
    )

    if send_new_message:
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=message,
            reply_markup=reply_markup,
            image_key=category.ui_image_key,
            fallback_image_key='default_catalog_account'
        )
        return

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=reply_markup,
        image_key=category.ui_image_key,
        fallback_image_key='default_catalog_account'
    )
