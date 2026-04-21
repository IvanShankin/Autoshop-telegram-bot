from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.application.models.modules import ProfileModule
from src.models.read_models.other import NotificationSettingsDTO
from src.infrastructure.translations import get_text


def profile_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "language"), callback_data='selecting_language')],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "notification"), callback_data='notification_settings')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data='profile')]
    ])


def settings_language_kb(language: str, profile_module: ProfileModule):
    keyboard = InlineKeyboardBuilder()

    for language in profile_module.conf.app.allowed_langs:
        is_current = (language == language)
        text = f"{'✔️ ' if is_current else ''}{profile_module.conf.app.name_langs[language]}  {profile_module.conf.app.emoji_langs[language]}"
        keyboard.add(InlineKeyboardButton(text=text, callback_data=f'language_selection:{language}'))

    keyboard.adjust(2)

    # добавляем кнопку "Назад" отдельной строкой
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data='profile_settings'))
    return keyboard.as_markup()


def setting_notification_kb(language: str, notification: NotificationSettingsDTO):
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
