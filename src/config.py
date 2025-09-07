import os
from dotenv import load_dotenv

load_dotenv()
TOKEN_BOT = os.getenv('TOKEN_BOT')
MAIN_ADMIN = int(os.getenv('MAIN_ADMIN'))


TYPE_PAYMENTS = {'crypto_bot': 'crypto_bot'}
TYPE_ACCOUNT_SERVICES = {'telegram': 'telegram', 'other': 'other'}


ALLOWED_LANGS = ["ru", "en"]

LOCALES_DIR = '../locales'
DEFAULT_LANG = "ru"

DT_FORMAT_FOR_LOGS = "%Y-%m-%d %H:%M:%S"

