import validators
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.models.update_models import UpdateSettingsDTO
from src.modules.admin_actions.keyboards import change_admin_settings_kb, back_in_change_admin_settings_kb
from src.modules.admin_actions.state.settings import UpdateAdminSettings
from src.utils.converter import safe_int_conversion
from src.infrastructure.translations import get_text


async def message_change_settings(
    user: UsersDTO,
    new_message: bool,
    admin_module: AdminModule,
    messages_service: Messages,
    callback: CallbackQuery = None,
):
    settings = await admin_module.settings_service.get_settings()

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
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=message,
            event_message_key="admin_panel",
            reply_markup=reply_markup
        )
        return

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        event_message_key="admin_panel",
        reply_markup=change_admin_settings_kb(user.language, current_maintenance_mode=settings.maintenance_mode)
    )


async def message_request_new_data(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, new_state: State, messages_service: Messages,
):
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_settings", "enter_new_data"),
        reply_markup=back_in_change_admin_settings_kb(user.language)
    )

    await state.set_state(new_state)


async def cheek_valid_data(state: str, message_text: str, user: UsersDTO, messages_service: Messages,) -> bool:
    """
    Проверит на валидность введённые пользователем данные
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
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=error_msg,
            reply_markup=back_in_change_admin_settings_kb(user.language)
        )
        return False

    return True


async def update_admin_settings(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages
):
    state = await state.get_state()
    message_text = message.text
    data_for_update = None

    if not await cheek_valid_data(state, message_text, user, messages_service):
        return

    if state == UpdateAdminSettings.support_username.state:
        data_for_update = UpdateSettingsDTO(support_username=message_text)

    elif state == UpdateAdminSettings.channel_for_logging_id.state:
        data_for_update = UpdateSettingsDTO(channel_for_logging_id=int(message_text))

    elif state == UpdateAdminSettings.channel_for_subscription_id.state:
        data_for_update = UpdateSettingsDTO(channel_for_subscription_id=int(message_text))

    elif state == UpdateAdminSettings.channel_for_subscription_url.state:
        data_for_update = UpdateSettingsDTO(channel_for_subscription_url=message_text)

    elif state == UpdateAdminSettings.channel_name.state:
        data_for_update = UpdateSettingsDTO(channel_name=message_text)

    elif state == UpdateAdminSettings.shop_name.state:
        data_for_update = UpdateSettingsDTO(shop_name=message_text)

    elif state == UpdateAdminSettings.faq_url.state:
        data_for_update = UpdateSettingsDTO(FAQ=message_text)

    if data_for_update:
        await admin_module.settings_service.update_settings(
            data=data_for_update,
            make_commit=True,
            filling_redis=True
        )

    await message_change_settings(user, new_message=True, messages_service=messages_service, admin_module=admin_module)



