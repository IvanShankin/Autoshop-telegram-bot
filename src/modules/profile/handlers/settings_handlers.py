from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.models.read_models.other import NotificationSettingsDTO, UsersDTO
from src.models.update_models import UpdateUserDTO, UpdateNotificationSettingDTO
from src.modules.profile.keyboards import profile_settings_kb, settings_language_kb, \
    setting_notification_kb
from src.services.bot import Messages
from src.services.models.modules import ProfileModule
from src.utils.i18n import get_text

router = Router()

async def notification_settings(
    user_id: int,
    message_id: int,
    messages_service: Messages,
    user: UsersDTO,
    notification: NotificationSettingsDTO
):
    await messages_service.edit_msg.edit(
        chat_id=user_id,
        message_id=message_id,
        message=get_text(user.language, "profile_messages", "notification_settings"),
        event_message_key='selecting_language',
        reply_markup=setting_notification_kb(user.language, notification=notification)
    )

async def language_settings(user_id: int, message_id: int, user: UsersDTO, messages_service: Messages):
    text = get_text(user.language, "profile_messages", "language_in_bot")

    await messages_service.edit_msg.edit(
        chat_id=user_id,
        message_id=message_id,
        message=text,
        event_message_key='selecting_language',
        reply_markup=settings_language_kb(user.language)
    )

@router.callback_query(F.data == "profile_settings")
async def profile_settings(
        callback: CallbackQuery, user: UsersDTO, messages_service: Messages
):
    text = get_text(user.language, "profile_messages", "select_settings_item")

    await messages_service.edit_msg.edit(
        chat_id = callback.from_user.id,
        message_id = callback.message.message_id,
        message = text,
        event_message_key = 'profile_settings',
        reply_markup = profile_settings_kb(user.language)
    )

@router.callback_query(F.data == "selecting_language")
async def open_language_settings(callback: CallbackQuery, user: UsersDTO, messages_service: Messages):
    await language_settings(
        user_id=callback.from_user.id,
        message_id=callback.message.message_id,
        user=user,
        messages_service=messages_service
    )

@router.callback_query(F.data.startswith('language_selection:'))
async def update_language(callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages):
    new_lang = callback.data.split(':')[1]

    await profile_module.user_service.update_user(
        user_id=user.user_id,
        data=UpdateUserDTO(language=new_lang),
        make_commit=True,
        filling_redis=True,
    )

    await language_settings(
        user_id=callback.from_user.id,
        message_id=callback.message.message_id,
        user=user,
        messages_service=messages_service,
    )

@router.callback_query(F.data == "notification_settings")
async def open_notification_settings(
    callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    notification = await profile_module.notification_service.get_notification(user_id=callback.from_user.id)

    await notification_settings(
        user_id=callback.from_user.id,
        user=user,
        message_id=callback.message.message_id,
        notification=notification,
        messages_service=messages_service,
    )

@router.callback_query(F.data.startswith('update_notif:'))
async def update_notification_settings(
    callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    column = callback.data.split(':')[1]
    new_value = True if callback.data.split(':')[2] == "True" else False

    notification = await profile_module.notification_service.get_notification(callback.from_user.id)

    if column == 'invitation':
        notification = await profile_module.notification_service.update_notifications(
            user_id=user.user_id,
            data=UpdateNotificationSettingDTO(referral_invitation=new_value)
        )
    elif column == "replenishment":
        notification = await profile_module.notification_service.update_notifications(
            user_id=user.user_id,
            data=UpdateNotificationSettingDTO(referral_replenishment=new_value)
        )

    await notification_settings(
        user_id=callback.from_user.id,
        user=user,
        message_id=callback.message.message_id,
        notification=notification,
        messages_service=messages_service,
    )