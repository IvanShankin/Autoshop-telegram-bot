import validators
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.modules.admin_actions.keyboards import change_admin_settings_kb, back_in_change_admin_settings_kb
from src.modules.admin_actions.state.settings import UpdateAdminSettings
from src.services.database.system.actions import get_settings, update_settings
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text


async def message_change_settings(user: Users, new_message: bool, callback: CallbackQuery = None):
    settings = await get_settings()

    message = get_text(
        user.language,
        "admins_settings",
        "settings_info"
    ).format(
        maintenance_mode='🟢' if settings.maintenance_mode else '🔴',
        support_username=settings.support_username,
        channel_for_logging_id=settings.channel_for_logging_id,
        channel_for_subscription_id=settings.channel_for_subscription_id,
        channel_for_subscription_url=settings.channel_for_subscription_url,
        channel_name=settings.channel_name,
        shop_name=settings.shop_name,
        FAQ=settings.FAQ,
    )

    reply_markup = change_admin_settings_kb(user.language, current_maintenance_mode=settings.maintenance_mode)

    if new_message:
        await send_message(
            chat_id=user.user_id,
            message=message,
            image_key="admin_panel",
            reply_markup=reply_markup
        )
        return

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        image_key="admin_panel",
        reply_markup=change_admin_settings_kb(user.language, current_maintenance_mode=settings.maintenance_mode)
    )


async def message_request_new_data(callback: CallbackQuery, state: FSMContext, user: Users, new_state: State):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_settings", "enter_new_data"),
        reply_markup=back_in_change_admin_settings_kb(user.language)
    )

    await state.set_state(new_state)


async def cheek_valid_data(state: str, message_text: str, user: Users) -> bool:
    """
    Проверит на валидность введённые пользователем данные
    :param state:
    :param message_text:
    :param user:
    :return: True если данные верны, иначе False
    """
    error_msg = None

    if (
            (state == UpdateAdminSettings.support_username.state
             or state == UpdateAdminSettings.shop_name.state
             or state == UpdateAdminSettings.faq_url.state)
            and len(message_text) > 150
    ):
        error_msg = get_text(user.language, "admins_settings", "text_too_long")

    if (
            (state == UpdateAdminSettings.channel_for_subscription_url.state
             or state == UpdateAdminSettings.faq_url.state)
            and not validators.url(message_text)
    ):
        error_msg = get_text(user.language, "admins_settings", "text_is_not_link")

    if (
            (state == UpdateAdminSettings.channel_for_logging_id.state
             or state == UpdateAdminSettings.channel_for_subscription_id.state)
            and not safe_int_conversion(message_text, positive=False)
    ):
        error_msg = get_text(user.language, "miscellaneous", "incorrect_value_entered")

    if error_msg:
        await send_message(
            chat_id=user.user_id,
            message=error_msg,
            reply_markup=back_in_change_admin_settings_kb(user.language)
        )
        return False

    return True


async def update_admin_settings(message: Message, state: FSMContext, user: Users):
    state = await state.get_state()
    message_text = message.text

    if not await cheek_valid_data(state, message_text, user):
        return

    if state == UpdateAdminSettings.support_username.state:
        await update_settings(support_username=message_text)

    elif state == UpdateAdminSettings.channel_for_logging_id.state:
        await update_settings(channel_for_logging_id=int(message_text))

    elif state == UpdateAdminSettings.channel_for_subscription_id.state:
        await update_settings(channel_for_subscription_id=int(message_text))

    elif state == UpdateAdminSettings.channel_for_subscription_url.state:
        await update_settings(channel_for_subscription_url=message_text)

    elif state == UpdateAdminSettings.channel_name.state:
        await update_settings(channel_name=message_text)

    elif state == UpdateAdminSettings.shop_name.state:
        await update_settings(shop_name=message_text)

    elif state == UpdateAdminSettings.faq_url.state:
        await update_settings(faq=message_text)

    await message_change_settings(user, new_message=True)















