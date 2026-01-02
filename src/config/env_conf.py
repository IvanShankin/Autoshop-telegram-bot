import os
from dotenv import load_dotenv

load_dotenv()


MAIN_ADMIN = int(os.getenv("MAIN_ADMIN"))
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
MODE = os.getenv("MODE")