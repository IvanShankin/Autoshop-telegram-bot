import os
import sys
from typing import List

from dotenv import load_dotenv
from pathlib import Path


load_dotenv()
TOKEN_BOT = os.getenv('TOKEN_BOT')
MAIN_ADMIN = int(os.getenv('MAIN_ADMIN'))
RABBITMQ_URL = os.getenv('RABBITMQ_URL')
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = "HS256"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
LOCALES_DIR = BASE_DIR / 'locales'
LOG_DIR =  BASE_DIR / 'logs'
MEDIA_DIR = BASE_DIR / "media"

TYPE_PAYMENTS = {'crypto_bot': 'crypto_bot'}
TYPE_ACCOUNT_SERVICES = {'telegram': 'telegram', 'other': 'other'}

ALLOWED_LANGS = ["ru", "en"] # все коды языков
EMOJI_LANGS = {"ru": "🇷🇺", "en": "🇬🇧", } # эмодзи по коду языка
NAME_LANGS = {"ru": "Русский", "en": "English", } # название языка по коду
DEFAULT_LANG = "ru"

DT_FORMAT = "%Y-%m-%d %H:%M:%S"

UI_IMAGES = {
    "welcome_message": f"{BASE_DIR}/media/ui_sections/welcome_message.png",
    "selecting_language": f"{BASE_DIR}/media/ui_sections/selecting_language.png",
    "successfully_activate_voucher": f"{BASE_DIR}/media/ui_sections/successfully_activate_voucher.png",
    "unsuccessfully_activate_voucher": f"{BASE_DIR}/media/ui_sections/unsuccessfully_activate_voucher.png",
    "new_referral": f"{BASE_DIR}/media/ui_sections/new_referral.png",
    "profile": f"{BASE_DIR}/media/ui_sections/profile.png",
    "profile_settings": f"{BASE_DIR}/media/ui_sections/profile_settings.png",
    "notification_settings": f"{BASE_DIR}/media/ui_sections/notification_settings.png",
    "history_transections": f"{BASE_DIR}/media/ui_sections/history_transections.png",
}
