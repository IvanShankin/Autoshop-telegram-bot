from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.modules.admin_actions.services.settings_updater import message_change_settings, message_request_new_data, \
    update_admin_settings
from src.modules.admin_actions.state.settings import UpdateAdminSettings
from src.services.database.system.actions import get_settings, update_settings
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data == "change_admin_settings")
async def change_admin_settings(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()

    await message_change_settings(user, new_message=False, callback=callback)


@router.callback_query(F.data.startswith("update_maintenance_mode"))
async def change_admin_settings(callback: CallbackQuery, user: Users):
    new_maintenance_mode = bool(int(callback.data.split(":")[1]))

    if not new_maintenance_mode:
        settings = await get_settings()

        if not settings.channel_for_logging_id:
            await callback.answer(
                get_text(user.language,"admins_settings", "First, please specify a chat/channel for logs"),
                show_alert=True
            )
            return

    await update_settings(maintenance_mode=new_maintenance_mode)
    await message_change_settings(user, new_message=False, callback=callback)


@router.callback_query(F.data == "update_support_username")
async def update_support_username(callback: CallbackQuery, state: FSMContext, user: Users):
    await message_request_new_data(callback, state, user, UpdateAdminSettings.support_username)


@router.callback_query(F.data == "update_channel_for_logging_id")
async def update_channel_for_logging_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await message_request_new_data(callback, state, user, UpdateAdminSettings.channel_for_logging_id)


@router.callback_query(F.data == "update_channel_for_subscription_id")
async def update_channel_for_subscription_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await message_request_new_data(callback, state, user, UpdateAdminSettings.channel_for_subscription_id)


@router.callback_query(F.data  ==  "update_channel_for_subscription_url")
async def update_channel_for_subscription_url(callback: CallbackQuery, state: FSMContext, user: Users):
    await message_request_new_data(callback, state, user, UpdateAdminSettings.channel_for_subscription_url)


@router.callback_query(F.data == "update_channel_name")
async def update_channel_name(callback: CallbackQuery, state: FSMContext, user: Users):
    await message_request_new_data(callback, state, user, UpdateAdminSettings.channel_name)


@router.callback_query(F.data == "update_shop_name")
async def update_shop_name(callback: CallbackQuery, state: FSMContext, user: Users):
    await message_request_new_data(callback, state, user, UpdateAdminSettings.shop_name)


@router.callback_query(F.data == "update_faq")
async def update_faq(callback: CallbackQuery, state: FSMContext, user: Users):
    await message_request_new_data(callback, state, user, UpdateAdminSettings.faq_url)


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
async def update_admin_settings_handler(message: Message, state: FSMContext, user: Users):
    await update_admin_settings(message, state, user)