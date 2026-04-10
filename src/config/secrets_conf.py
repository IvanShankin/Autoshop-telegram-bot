from pydantic import BaseModel

from src.application.crypto.secrets_storage import GetSecret


class SecretSettings(BaseModel):
    token_bot: str
    token_logger_bot: str
    token_crypto_bot: str
    db_password: str


def load_secrets(get_secret: GetSecret) -> SecretSettings:
    """Данные переменные могут браться как из .env, так и из удалённого хранилища секретов"""
    return SecretSettings(
        token_bot=get_secret.execute("TOKEN_BOT"),
        token_logger_bot=get_secret.execute("TOKEN_LOGGER_BOT"),
        token_crypto_bot=get_secret.execute("TOKEN_CRYPTO_BOT"),
        db_password=get_secret.execute("DB_PASSWORD"),
    )
