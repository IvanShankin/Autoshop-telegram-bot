import os
import sys

from dotenv import load_dotenv
from pathlib import Path


load_dotenv()

TOKEN_BOT = os.getenv('TOKEN_BOT')
TOKEN_LOGGER_BOT = os.getenv('TOKEN_LOGGER_BOT')
TOKEN_CRYPTO_BOT = os.getenv('TOKEN_CRYPTO_BOT')

MAIN_ADMIN = int(os.getenv('MAIN_ADMIN'))
RABBITMQ_URL = os.getenv('RABBITMQ_URL')
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = "HS256"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
LOCALES_DIR = BASE_DIR / 'locales'
LOG_DIR =  BASE_DIR / 'logs'
MEDIA_DIR = BASE_DIR / "media"
ACCOUNTS_DIR = MEDIA_DIR / "accounts"
TEMP_FILE_DIR = MEDIA_DIR / "temp"

TYPE_PAYMENTS = ['crypto_bot', 'zelenka'] # отображают в типах оплаты для админа
MIN_MAX_REPLENISHMENT = {'crypto_bot': {"min": 1, "max": 99999999}}
TYPE_ACCOUNT_SERVICES = ['telegram', 'other']

ALLOWED_LANGS = ["ru", "en"] # все коды языков
EMOJI_LANGS = {"ru": "🇷🇺", "en": "🇬🇧", } # эмодзи по коду языка
NAME_LANGS = {"ru": "Русский", "en": "English", } # название языка по коду
DEFAULT_LANG = "ru"

SUPPORTED_ARCHIVE_EXTENSIONS = ["zip"]

DT_FORMAT = "%Y-%m-%d %H:%M:%S"
PAYMENT_LIFETIME_SECONDS = 1200 # 20 минут
FETCH_INTERVAL = 7200 # 2 часа (для обновления курса доллара)

PAGE_SIZE = 6

MAX_SIZE_MB = 10
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024  # 10 мегабайт = 10 * 1024 * 1024
MAX_DOWNLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_UPLOAD_FILE = 49 * 1024 * 1024  # 49 MB (с запасом)