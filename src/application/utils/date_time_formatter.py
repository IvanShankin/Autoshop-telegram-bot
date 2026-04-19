from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from src.config import Config


class DateTimeFormatter:
    def __init__(self, conf: Config, default_tz: str = "Europe/Moscow"):
        self.default_tz = default_tz
        self.conf = conf

    def format(self, dt: datetime, tz: Optional[str] = None, fmt: Optional[str] = None) -> str:
        """Преобразует дату в формат для пользователя"""
        tz = tz or self.default_tz
        fmt = fmt or self.conf.different.dt_format

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(ZoneInfo(tz)).strftime(fmt)