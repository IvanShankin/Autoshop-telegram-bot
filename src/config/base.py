from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def init_env(env_name: Optional[str] = None) -> None:
    if env_name:
        load_dotenv(dotenv_path=env_name, override=False)