from dotenv import load_dotenv

from src.services.secrets.loader import get_secret
from src.services.secrets.shemas import SecretSettings

load_dotenv()

_settings: SecretSettings | None = None


def get_secret_conf() -> SecretSettings:
    global _settings

    if _settings is None:
        _settings = SecretSettings(
            TOKEN_BOT=get_secret("TOKEN_BOT"),
            TOKEN_LOGGER_BOT=get_secret("TOKEN_LOGGER_BOT"),
            TOKEN_CRYPTO_BOT=get_secret("TOKEN_CRYPTO_BOT")
        )

    return _settings
