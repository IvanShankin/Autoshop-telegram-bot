import os
import sys

from dotenv import load_dotenv
from pathlib import Path


load_dotenv()
TOKEN_BOT = os.getenv('TOKEN_BOT')
MAIN_ADMIN = int(os.getenv('MAIN_ADMIN'))
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = "HS256"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
LOCALES_DIR = BASE_DIR / 'locales'
LOG_DIR =  BASE_DIR / 'logs'

TYPE_PAYMENTS = {'crypto_bot': 'crypto_bot'}
TYPE_ACCOUNT_SERVICES = {'telegram': 'telegram', 'other': 'other'}
ALLOWED_LANGS = ["ru", "en"]
DEFAULT_LANG = "ru"

DT_FORMAT_FOR_LOGS = "%Y-%m-%d %H:%M:%S"

