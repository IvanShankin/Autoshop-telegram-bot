from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def init_env(env_path_name: Optional[str] = None) -> None:
    if env_path_name:
        load_dotenv(dotenv_path=env_path_name, override=False)
        return

    load_dotenv(override=False)