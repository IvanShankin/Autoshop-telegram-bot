import enum


class LogLevel(enum.Enum):
    """исключения логировать сразу"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
