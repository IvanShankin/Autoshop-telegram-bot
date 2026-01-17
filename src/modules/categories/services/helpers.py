from src.bot_actions.bot_instance import get_bot
from src.bot_actions.messages import edit_message, send_message
from src.modules.categories.keyboards.keyboard_categories import account_category_kb
from src.modules.categories.shemas import BuyProductsData
from src.services.database.categories.actions import get_categories_by_category_id
from src.services.database.categories.models import CategoryFull
from src.services.database.system.actions import get_ui_image
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def check_category(category_id: int, old_message_id: int, user_id: int, language: str) -> CategoryFull | None:
    """
    Если есть категория, то вернёт её, если не найдена, то отошлёт соответсвующее сообщение и удалит прошлое
    :return: Если есть категория, то вернёт CategoryFull, иначе None
    """
    category = await get_categories_by_category_id(category_id, language=language)
    if not category:
        try:
            bot = await get_bot()
            await bot.delete_message(user_id, old_message_id)
        except Exception:
            pass

        await send_message(
            chat_id=user_id,
            message=get_text(language, 'categories',"The category is temporarily unavailable"),
        )
        return None

    return category


async def edit_message_category(
        user: Users,
        message_id: int,
        data: BuyProductsData,
        category: CategoryFull
):
    ui_image = await get_ui_image(category.ui_image_key)

    message = None
    if category.is_product_storage:
        message_discount = ''
        total_price = data.quantity_for_buying * category.price

        # расчёт скидки
        if data.promo_code:
            if data.promo_code_amount:
                # если скида фиксированное число
                discount = data.promo_code_amount
            else:
                # если скидка в процентах
                discount = (data.quantity_for_buying * category.price) * data.discount_percentage / 100

            total_price = max(0, total_price - discount)
            message_discount = get_text(user.language, 'categories',"Discount with promo code: {discount}\n").format(discount=discount)

        message = get_text(
            user.language,
            'categories',
            "{name} \n\n"
            "Description: {description}\n"
            "Price per product: {price} ₽ \n\n"
            "Products selected: {selected_products}\n"
            "{discount}"
            "Total: {total_price}\n\n"
            "To specify the required quantity, send the bot a number"
        ).format(
            name=category.name,
            description=category.description,
            price=category.price,
            selected_products=data.quantity_for_buying,
            discount=message_discount,
            total_price=total_price
        )

    await edit_message(
        chat_id=user.user_id,
        message_id=message_id,
        message=message,
        image_key=category.ui_image_key if (ui_image and ui_image.show) else 'default_catalog_account',
        reply_markup=await account_category_kb(
            user.language,
            category=category,
            quantity_for_buying=data.quantity_for_buying,
            promo_code_id=data.promo_code_id
        )
    )