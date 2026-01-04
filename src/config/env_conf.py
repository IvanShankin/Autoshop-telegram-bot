from enum import Enum
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

    @classmethod
    def from_env(cls) -> "EnvSettings":
        return cls(
            main_admin=int(os.environ["MAIN_ADMIN"]),
            rabbitmq_url=os.environ["RABBITMQ_URL"],
            storage_server_url=os.environ["STORAGE_SERVER_URL"],
            redis_host=os.environ["REDIS_HOST"],
            redis_port=os.environ["REDIS_PORT"],
            mode=Mode(os.environ["MODE"]),
            db_host=os.getenv('DB_HOST'),
            db_user = os.getenv('DB_USER'),
            db_name = os.getenv('DB_NAME')

        )
