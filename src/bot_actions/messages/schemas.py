import enum
from typing import Optional

from pydantic import BaseModel



class LogLevel(enum.Enum):
    """исключения логировать сразу"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EventSentLog(BaseModel):
    text: str
    log_lvl: Optional[LogLevel] = None
    channel_for_logging_id: int = None