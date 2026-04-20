from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO, LogLevel
from src.models.update_models import UpdateSettingsDTO
from src.modules.admin_actions.services.settings_updater import message_change_settings, message_request_new_data, \
    update_admin_settings
from src.modules.admin_actions.state.settings import UpdateAdminSettings
from src.infrastructure.translations import get_text

router = Router()


@router.callback_query(F.data == "change_admin_settings")
async def change_admin_settings(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    await state.clear()

    await message_change_settings(
        user, new_message=False, callback=callback, messages_service=messages_service, admin_module=admin_module
    )


@router.callback_query(F.data.startswith("update_maintenance_mode"))
async def change_admin_settings(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    new_maintenance_mode = bool(int(callback.data.split(":")[1]))

    if not new_maintenance_mode:
        settings = await admin_module.settings_service.get_settings()

        if not settings.channel_for_logging_id:
            await callback.answer(
                get_text(user.language,"admins_settings", "first_specify_log_chat"),
                show_alert=True
            )
            return

    await admin_module.settings_service.update_settings(
        data=UpdateSettingsDTO(maintenance_mode=new_maintenance_mode),
        make_commit=True,
        filling_redis=True,
    )
    await message_change_settings(
        user, new_message=False, callback=callback, messages_service=messages_service, admin_module=admin_module
    )

    await admin_module.publish_event_handler.send_log(
        text="⚠️Режим 'Технические работы' включён⚠️" if new_maintenance_mode else "⚙️Режим 'Технические работы' выключен⚙️",
        log_lvl=LogLevel.WARNING,
    )


@router.callback_query(F.data == "update_support_username")
async def update_support_username(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await message_request_new_data(
        callback, state, user, UpdateAdminSettings.support_username, messages_service
    )


@router.callback_query(F.data == "update_channel_for_logging_id")
async def update_channel_for_logging_id(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await message_request_new_data(
        callback, state, user, UpdateAdminSettings.channel_for_logging_id, messages_service
    )


@router.callback_query(F.data == "update_channel_for_subscription_id")
async def update_channel_for_subscription_id(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await message_request_new_data(
        callback, state, user, UpdateAdminSettings.channel_for_subscription_id, messages_service
    )


@router.callback_query(F.data  ==  "update_channel_for_subscription_url")
async def update_channel_for_subscription_url(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await message_request_new_data(
        callback, state, user, UpdateAdminSettings.channel_for_subscription_url, messages_service
    )


@router.callback_query(F.data == "update_channel_name")
async def update_channel_name(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await message_request_new_data(callback, state, user, UpdateAdminSettings.channel_name, messages_service)


@router.callback_query(F.data == "update_shop_name")
async def update_shop_name(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await message_request_new_data(
        callback, state, user, UpdateAdminSettings.shop_name, messages_service
    )


@router.callback_query(F.data == "update_faq")
async def update_faq(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await message_request_new_data(
        callback, state, user, UpdateAdminSettings.faq_url, messages_service
    )


@router.message(
    StateFilter(
        UpdateAdminSettings.support_username,
        UpdateAdminSettings.channel_for_logging_id,
        UpdateAdminSettings.channel_for_subscription_id,
        UpdateAdminSettings.channel_for_subscription_url,
        UpdateAdminSettings.channel_name,
        UpdateAdminSettings.shop_name,
        UpdateAdminSettings.faq_url,
    )
)
async def update_admin_settings_handler(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    await update_admin_settings(message, state, user, admin_module, messages_service)