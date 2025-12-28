import os
from dotenv import load_dotenv


load_dotenv()

TOKEN_BOT = os.getenv('TOKEN_BOT')
TOKEN_LOGGER_BOT = os.getenv('TOKEN_LOGGER_BOT')
TOKEN_CRYPTO_BOT = os.getenv('TOKEN_CRYPTO_BOT')

MAIN_ADMIN = int(os.getenv('MAIN_ADMIN'))
RABBITMQ_URL = os.getenv('RABBITMQ_URL')
ALGORITHM = "HS256"