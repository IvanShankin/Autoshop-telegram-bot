from enum import Enum
from typing import Optional

from pydantic import BaseModel
import os


class Mode(str, Enum):
    DEV = "DEV"
    PROD = "PROD"
    TEST = "TEST"


class EnvSettings(BaseModel):
    main_admin: int

    rabbitmq_url: str
    storage_server_url: str

    redis_host: str
    redis_port: str

    db_host: str
    db_user: str
    db_name: str

    mode: Mode

    use_secret_storage: bool
    cert_dir: Optional[str] = None

    @classmethod
    def from_env(cls) -> "EnvSettings":
        use_secret_storage_str = os.getenv('USE_SECRET_STORAGE')
        use_secret_storage_str = use_secret_storage_str.lower() if use_secret_storage_str else False
        use_secret_storage = True if use_secret_storage_str == "true" else False

        return cls(
            main_admin=int(os.environ["MAIN_ADMIN"]),
            rabbitmq_url=os.environ["RABBITMQ_URL"],
            storage_server_url=os.environ["STORAGE_SERVER_URL"],
            redis_host=os.environ["REDIS_HOST"],
            redis_port=os.environ["REDIS_PORT"],
            mode=Mode(os.environ["MODE"]),
            db_host=os.getenv('DB_HOST'),
            db_user=os.getenv('DB_USER'),
            db_name=os.getenv('DB_NAME'),
            use_secret_storage=use_secret_storage,
            cert_dir=os.getenv('CERT_DIR')
        )
