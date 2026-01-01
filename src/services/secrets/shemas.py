from pydantic import BaseModel


class SecretSettings(BaseModel):
    TOKEN_BOT: str
    TOKEN_LOGGER_BOT: str
    TOKEN_CRYPTO_BOT: str

    MAIN_ADMIN: int
    RABBITMQ_URL: str
