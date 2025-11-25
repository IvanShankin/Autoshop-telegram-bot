import asyncio

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot_actions.actions import send_message
from src.exceptions.service_exceptions import IncorrectedAmountSale, IncorrectedCostPrice, \
    IncorrectedNumberButton
from src.modules.admin_actions.handlers.editor.category.show_handlers import show_category_update_data
from src.modules.admin_actions.schemas.editor_categories import UpdateCategoryOnlyId
from src.modules.admin_actions.state.editor_categories import UpdateNumberInCategory
from src.services.database.selling_accounts.actions import update_account_category
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text


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


