from dotenv import load_dotenv

from src.services.secrets.loader import get_secret

load_dotenv()

TOKEN_BOT = get_secret('TOKEN_BOT')
TOKEN_LOGGER_BOT = get_secret('TOKEN_LOGGER_BOT')
TOKEN_CRYPTO_BOT = get_secret('TOKEN_CRYPTO_BOT')

MAIN_ADMIN = int(get_secret('MAIN_ADMIN'))
RABBITMQ_URL = get_secret('RABBITMQ_URL')
