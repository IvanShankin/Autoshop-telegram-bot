from pydantic import BaseModel
from src.services.secrets.loader import get_secret


class SecretSettings(BaseModel):
    token_bot: str
    token_logger_bot: str
    token_crypto_bot: str


def load_secrets() -> SecretSettings:
    return SecretSettings(
        token_bot=get_secret("TOKEN_BOT"),
        token_logger_bot=get_secret("TOKEN_LOGGER_BOT"),
        token_crypto_bot=get_secret("TOKEN_CRYPTO_BOT"),
    )
