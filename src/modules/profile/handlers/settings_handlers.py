from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.modules.profile.keyboards import profile_settings_kb, settings_language_kb, \
    setting_notification_kb
from src.services.database.users.actions import get_user, update_user
from src.services.database.users.actions.action_other_with_user import get_notification, update_notification
from src.services.database.users.models import NotificationSettings, Users
from src.utils.i18n import get_text

router = Router()

async def notification_settings(user_id: int, username: str, message_id: int, notification: NotificationSettings):
    user = await get_user(user_id, username)

    await edit_message(
        chat_id=user_id,
        message_id=message_id,
        message=get_text(user.language, 'profile_messages', "Notification Settings"),
        image_key='selecting_language',
        reply_markup=setting_notification_kb(user.language, notification=notification)
    )

async def language_settings(user_id: int, message_id: int, user: Users):
    text = get_text(user.language, 'profile_messages', "Language in the bot")

    await edit_message(
        chat_id=user_id,
        message_id=message_id,
        message=text,
        image_key='selecting_language',
        reply_markup=settings_language_kb(user.language)
    )

@router.callback_query(F.data == "profile_settings")
async def profile_settings(callback: CallbackQuery, user: Users):
    text = get_text(user.language, 'profile_messages', "Select the settings item")

    await edit_message(
        chat_id = callback.from_user.id,
        message_id = callback.message.message_id,
        message = text,
        image_key = 'profile_settings',
        reply_markup = profile_settings_kb(user.language)
    )

@router.callback_query(F.data == "selecting_language")
async def open_language_settings(callback: CallbackQuery, user: Users):
    await language_settings(
        user_id=callback.from_user.id,
        message_id=callback.message.message_id,
        user=user
    )

@router.callback_query(F.data.startswith('language_selection:'))
async def update_language(callback: CallbackQuery, user: Users):
    new_lang = callback.data.split(':')[1]

    user = await update_user(user_id=user.user_id, language=new_lang)

    await language_settings(
        user_id=callback.from_user.id,
        message_id=callback.message.message_id,
        user=user
    )

@router.callback_query(F.data == "notification_settings")
async def open_notification_settings(callback: CallbackQuery):
    notification = await get_notification(callback.from_user.id)
    await notification_settings(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        message_id=callback.message.message_id,
        notification=notification
    )

@router.callback_query(F.data.startswith('update_notif:'))
async def update_notification_settings(callback: CallbackQuery, user: Users):
    column = callback.data.split(':')[1]
    new_value = True if callback.data.split(':')[2] == "True" else False

    notification = await get_notification(callback.from_user.id)

    if column == 'invitation':
        notification = await update_notification(
            user.user_id,
            referral_invitation=new_value,
            referral_replenishment=notification.referral_replenishment
        )
    elif column == 'replenishment':
        notification = await update_notification(
            user.user_id,
            referral_invitation=notification.referral_invitation,
            referral_replenishment=new_value
        )

    await notification_settings(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        message_id=callback.message.message_id,
        notification=notification
    )