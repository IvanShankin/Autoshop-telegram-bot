from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.database.users.models import NotificationSettings
from src.utils.i18n import get_text


def profile_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "language"), callback_data='selecting_language')],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "notification"), callback_data='notification_settings')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data='profile')]
    ])


def settings_language_kb(language: str):
    keyboard = InlineKeyboardBuilder()

    for lang in get_config().app.allowed_langs:
        is_current = (lang == language)
        text = f"{'✔️ ' if is_current else ''}{get_config().app.name_langs[lang]}  {get_config().app.emoji_langs[lang]}"
        keyboard.add(InlineKeyboardButton(text=text, callback_data=f'language_selection:{lang}'))

    keyboard.adjust(2)

    # добавляем кнопку "Назад" отдельной строкой
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data='profile_settings'))
    return keyboard.as_markup()


def setting_notification_kb(language: str, notification: NotificationSettings):
    return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                text=f'{"✔️ " if notification.referral_invitation else ''}{get_text(language, "kb_profile", "new_referral")}',
                callback_data=f'update_notif:invitation:{"False" if notification.referral_invitation else 'True'}')
            ],
            [
                InlineKeyboardButton(
                    text=f'{"✔️ " if notification.referral_replenishment else ''}{get_text(language, "kb_profile", "replenishment_referral")}',
                    callback_data=f'update_notif:replenishment:{"False" if notification.referral_replenishment else 'True'}')
            ],
            [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data='profile_settings')]
        ])
