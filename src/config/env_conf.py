# import os
# from dotenv import load_dotenv
#
# load_dotenv()
#
#
# MAIN_ADMIN = int(os.getenv("MAIN_ADMIN"))
# RABBITMQ_URL = os.getenv("RABBITMQ_URL")
# MODE = os.getenv("MODE")
from pathlib import Path

########################################################################################################################
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum


BASE_DIR = Path(__file__).resolve().parent.parent.parent

# class EnvSettings(BaseSettings):
#     main_admin: int
#     rabbitmq_url: str
#     mode: Mode
#
#     model_config = {
#         "env_file": BASE_DIR / ".env",
#         "env_file_encoding": "utf-8",
#         "case_sensitive": True,
#         "extra": "ignore",
#
#     }

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
    mode: Mode

    @classmethod
    def from_env(cls) -> "EnvSettings":
        return cls(
            main_admin=int(os.environ["MAIN_ADMIN"]),
            rabbitmq_url=os.environ["RABBITMQ_URL"],
            mode=Mode(os.environ["MODE"]),
        )
