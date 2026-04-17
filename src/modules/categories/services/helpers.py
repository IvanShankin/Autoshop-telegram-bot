from src.application.bot import Messages
from src.application.models.modules import CatalogModule
from src.infrastructure.telegram.bot_client import TelegramClient
from src.modules.categories.keyboards import account_category_kb
from src.modules.categories.shemas import BuyProductsData
from src.models.read_models import CategoryFull
from src.database.models.users import Users
from src.utils.i18n import get_text


async def check_category(
    category_id: int,
    old_message_id: int,
    user_id: int, language: str,
    messages_service: Messages,
    catalog_modul: CatalogModule,
    tg_client: TelegramClient,
) -> CategoryFull | None:
    """
    Если есть категория, то вернёт её, если не найдена, то отошлёт соответсвующее сообщение и удалит прошлое
    :return: Если есть категория, то вернёт CategoryFull, иначе None
    """
    category = await catalog_modul.category_service.get_category_by_id(category_id, language=language)
    if not category:
        try:
            await tg_client.delete_message(user_id, old_message_id)
        except Exception:
            pass

        await messages_service.send_msg.send(
            chat_id=user_id,
            message=get_text(language, "categories","category_temporarily_unavailable"),
        )
        return None

    return category


async def edit_message_category(
    user: Users,
    message_id: int,
    data: BuyProductsData,
    category: CategoryFull,
    messages_service: Messages,
    catalog_modul: CatalogModule
):
    ui_image = await catalog_modul.ui_image_service.get_ui_image(category.ui_image_key)

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
            message_discount = get_text(user.language, "categories","promo_code_discount").format(discount=discount)

        message = get_text(
            user.language,
            "categories",
            "product_selection_info"
        ).format(
            name=category.name,
            description=category.description,
            price=category.price,
            selected_products=data.quantity_for_buying,
            discount=message_discount,
            total_price=total_price
        )

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=message_id,
        message=message,
        image_key=category.ui_image_key if (ui_image and ui_image.show) else 'default_catalog_account',
        reply_markup=await account_category_kb(
            user.language,
            category=category,
            quantity_for_buying=data.quantity_for_buying,
            promo_code_id=data.promo_code_id,
            catalog_modul=catalog_modul,
        )
    )