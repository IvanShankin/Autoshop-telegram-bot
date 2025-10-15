from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import ALLOWED_LANGS, NAME_LANGS, EMOJI_LANGS
from src.services.users.models import NotificationSettings
from src.utils.i18n import get_i18n


def profile_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Top up your balance'), callback_data='money_replenishment')],
        [InlineKeyboardButton(text=i18n.gettext('Purchased accounts'), callback_data='purchased_accounts')],
        [InlineKeyboardButton(text=i18n.gettext('Balance transfer'), callback_data='balance_transfer')],
        [InlineKeyboardButton(text=i18n.gettext('Referral system'), callback_data='referral_system')],
        [InlineKeyboardButton(text=i18n.gettext('History transfer'), callback_data='history_transaction')],
        [InlineKeyboardButton(text=i18n.gettext('Settings'), callback_data='profile_settings')]
    ])

def profile_settings_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Language'), callback_data='selecting_language')],
        [InlineKeyboardButton(text=i18n.gettext('Notification'), callback_data='notification_settings')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='profile')]
    ])

def settings_language_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    keyboard = InlineKeyboardBuilder()

    for lang in ALLOWED_LANGS:
        is_current = (lang == language)
        text = f"{'✔️ ' if is_current else ''}{NAME_LANGS[lang]}  {EMOJI_LANGS[lang]}"
        keyboard.add(InlineKeyboardButton(text=text, callback_data=f'language_selection:{lang}'))

    keyboard.adjust(2)

    # добавляем кнопку "Назад" отдельной строкой
    keyboard.row(InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='profile_settings'))
    return keyboard.as_markup()

async def setting_notification_kb(language: str, notification: NotificationSettings):
    i18n = get_i18n(language, 'keyboard_dom')

    return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                text=f'{"✔️ " if notification.referral_invitation else ''}{i18n.gettext("New referral")}',
                callback_data=f'update_notif:invitation:{"False" if notification.referral_invitation else 'True'}')
            ],
            [
                InlineKeyboardButton(
                    text=f'{"✔️ " if notification.referral_replenishment else ''}{i18n.gettext("Replenishment referral")}',
                    callback_data=f'update_notif:replenishment:{"False" if notification.referral_replenishment else 'True'}')
            ],
            [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='profile_settings')]
        ])

