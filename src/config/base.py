from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def init_env() -> None:
    load_dotenv(BASE_DIR / ".env", override=True)