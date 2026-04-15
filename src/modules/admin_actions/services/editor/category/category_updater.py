import asyncio

from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.exceptions import IncorrectedAmountSale, IncorrectedCostPrice, \
    IncorrectedNumberButton, AccountCategoryNotFound, TheCategoryStorageAccount, CategoryStoresSubcategories
from src.models.read_models import UsersDTO
from src.models.update_models.category import UpdateCategory
from src.modules.admin_actions.schemas import UpdateCategoryOnlyId
from src.modules.admin_actions.services.editor.category.show_message import show_category_update_data, show_category
from src.modules.admin_actions.state import UpdateNumberInCategory
from src.database.models.categories import ProductType, AccountServiceType, UniversalMediaType
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text


async def update_data(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages
):
    """Обновляет цену за один аккаунт, себестоимость одного аккаунта, число кнопок в строке (только одно)"""
    data = UpdateCategoryOnlyId(**(await state.get_data()))
    new_number = safe_int_conversion(message.text)
    message_error = None

    try:
        await message.delete()
    except Exception:
        pass

    if new_number is None:
        message_error = get_text(user.language, "miscellaneous", "incorrect_value_entered")
    else:
        try:
            new_data = None

            if await state.get_state() == UpdateNumberInCategory.price.state:
                new_data = UpdateCategory(price=new_number)
            elif await state.get_state() == UpdateNumberInCategory.cost_price.state:
                new_data = UpdateCategory(cost_price=new_number)
            elif await state.get_state() == UpdateNumberInCategory.number_button.state:
                new_data = UpdateCategory(number_buttons_in_row=new_number)

            if new_data:
                await admin_module.category_service.update_category(data.category_id, data=new_data)

        except (IncorrectedAmountSale, IncorrectedCostPrice, IncorrectedNumberButton):
            message_error = get_text(user.language, "miscellaneous", "incorrect_value_entered")

    if message_error:
        message_error += '\n\n'
        message_error += get_text(user.language, "miscellaneous", "try_again")

        await messages_service.send_msg.send(chat_id=user.user_id, message=message_error)

        if await state.get_state() == UpdateNumberInCategory.price.state:
            await state.set_state(UpdateNumberInCategory.price)
        elif await state.get_state() == UpdateNumberInCategory.cost_price.state:
            await state.set_state(UpdateNumberInCategory.cost_price)
        elif await state.get_state() == UpdateNumberInCategory.number_button.state:
            await state.set_state(UpdateNumberInCategory.number_button)

        return

    await show_category_update_data(
        user, data.category_id, send_new_message=True, admin_module=admin_module, messages_service=messages_service
    )
    message_info = await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(user.language, "miscellaneous","data_updated_successfully")
    )

    await asyncio.sleep(3)
    try:
        await message_info.delete()
    except Exception:
        pass


async def update_category_storage(
    category_id: int,
    is_storage: bool,
    user: UsersDTO,
    callback: CallbackQuery,
    admin_module: AdminModule,
    messages_service: Messages,
    product_type: ProductType | None = None,
    type_account_service: AccountServiceType | None = None,
    media_type: UniversalMediaType | None = None,
):
    """
    Обновит у категории возможность хранения продукта и выведет сообщение с результатом

    Если передать is_storage == True, то необходимо указать product_type.
    Если product_type - это аккаунты, то необходимо передать type_account_service.
    При несоблюдении любого требования будет вызвано исключение ValueError

    :raise ValueError:
    """
    update_value = UpdateCategory()

    if is_storage:
        if product_type:
            update_value.product_type = product_type
        if type_account_service:
            update_value.type_account_service = type_account_service
        if media_type:
            update_value.media_type = media_type

    update_value.is_product_storage = is_storage

    try:
        await admin_module.category_service.update_category(category_id, data=update_value)
        message = get_text(user.language, "miscellaneous", "successfully_updated")
    except AccountCategoryNotFound:
        try:
            await callback.message.delete()
        except Exception:
            pass
        message = get_text(user.language, "admins_editor_category", "category_not_exists")
    except TheCategoryStorageAccount:
        message = get_text(user.language, "admins_editor_category","extract_accounts_stored_in_category")
    except CategoryStoresSubcategories:
        message = get_text(user.language, "admins_editor_category","first_delete_subcategory")

    await callback.answer(message, show_alert=True)
    await show_category(
        user=user,
        category_id=category_id,
        message_id=callback.message.message_id,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service
    )

