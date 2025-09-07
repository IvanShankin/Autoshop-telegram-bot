import os
import sys

from dotenv import load_dotenv
from pathlib import Path



load_dotenv()
TOKEN_BOT = os.getenv('TOKEN_BOT')
MAIN_ADMIN = int(os.getenv('MAIN_ADMIN'))

TYPE_PAYMENTS = {'crypto_bot': 'crypto_bot'}
TYPE_ACCOUNT_SERVICES = {'telegram': 'telegram', 'other': 'other'}

ALLOWED_LANGS = ["ru", "en"]


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

LOCALES_DIR = BASE_DIR / 'locales'
DEFAULT_LANG = "ru"

DT_FORMAT_FOR_LOGS = "%Y-%m-%d %H:%M:%S"

