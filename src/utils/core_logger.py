import logging
from src.config import LOG_DIR

LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "auth_service.log",encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)