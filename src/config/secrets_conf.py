from typing import Callable
from pydantic import BaseModel


class SecretSettings(BaseModel):
    token_bot: str
    token_logger_bot: str
    token_crypto_bot: str
    db_password: str



def load_secrets(get_secret: Callable[[str], str]) -> SecretSettings:
    return SecretSettings(
        token_bot=get_secret("TOKEN_BOT"),
        token_logger_bot=get_secret("TOKEN_LOGGER_BOT"),
        token_crypto_bot=get_secret("TOKEN_CRYPTO_BOT"),
        db_password=get_secret("DB_PASSWORD"),
    )