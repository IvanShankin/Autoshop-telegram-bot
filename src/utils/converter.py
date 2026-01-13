from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from asyncpg.pgproto.pgproto import timedelta

DEFAULT_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
]

DEFAULT_TIME_FORMATS = [
    "%H:%M:%S",
    "%H:%M",
]

DEFAULT_DATETIME_FORMATS = [
    f"{d} {t}"
    for d in DEFAULT_DATE_FORMATS
    for t in DEFAULT_TIME_FORMATS
] + DEFAULT_DATE_FORMATS + DEFAULT_TIME_FORMATS


def safe_parse_datetime(
    value: str,
    default = None,
    only_date: bool = False,
    only_time: bool = False,
    min_date=None,
    max_date=None,
    formats=None,
):
    """
    :param value: строка с датой и/или временем
    :param default: значение по умолчанию при ошибке
    :param only_date: вернуть только date
    :param only_time: вернуть только time
    :param min_date: минимально допустимая дата
    :param max_date: максимальный допустимая дата
    :param formats: необязательный список форматов для перебора
    """
    if not value or not isinstance(value, str):
        return default

    if min_date is None:
        min_date = datetime.now(timezone.utc)
    if max_date is None:
        max_date = datetime.now(timezone.utc) + timedelta(days=36500)

    value = value.strip()
    if not value:
        return default

    formats = formats or DEFAULT_DATETIME_FORMATS

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)

            # Делаем дату UTC-aware
            local_tz = ZoneInfo("Europe/Moscow") # utc делаем по московскому времени
            parsed = parsed.replace(tzinfo=local_tz).astimezone(timezone.utc)

            # Проверка диапазона
            if not (min_date <= parsed <= max_date):
                continue

            if only_date:
                return parsed.date()

            if only_time:
                return parsed.time()

            return parsed

        except ValueError:
            continue

    return default

def safe_int_conversion(value, default=None, positive=False) -> int:
    """Попытается преобразовать в int, если не получится, то вернёт аргумент default, иначе преобразованное число"""
    try:
        value_in_int = int(value)
        if value_in_int > 123456789012345678901234567890: # если больше BigInt
            return default
        if positive:
            return value_in_int if value_in_int > 0 else default

        return value_in_int
    except (ValueError, TypeError):
        return default


def safe_float_conversion(value, default=None, positive=False) -> float:
    """Попытается преобразовать в float, если не получится, то вернёт аргумент default, иначе преобразованное число"""
    try:
        value_in_float = float(value)
        if value_in_float > 123456789012345678901234567890: # если больше BigInt
            return default
        if positive:
            return value_in_float if value_in_float > 0 else default

        return value_in_float
    except (ValueError, TypeError):
        return default
