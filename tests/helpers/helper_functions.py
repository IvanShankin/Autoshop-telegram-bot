from datetime import datetime
from typing import Type
from dateutil.parser import parse

async def comparison_models(Expected: Type | dict, Actual: Type | dict, keys_not_checked: list = []):
    """Сравнивает две модели БД"""
    if not isinstance(Expected, dict):
        Expected: dict = Expected.to_dict()
    if not isinstance(Actual, dict):
        Actual: dict = Actual.to_dict()

    for key in Expected.keys():
        if not key in keys_not_checked:
            # если ожидаемый результат должен быть датой, и актуальный является не датой
            if isinstance(Expected[key], datetime) and not isinstance(Actual[key], datetime):
                assert Expected[key] == parse(Actual[key])
            else:
                assert Expected[key] == Actual[key],f'ключ "{key}" не совпал'


def parse_redis_user(redis_bytes: bytes) -> dict:
    """Десериализация user из Redis с конвертацией даты"""
    import orjson
    from dateutil.parser import parse

    data = orjson.loads(redis_bytes)
    if "created_at" in data and isinstance(data["created_at"], str):
        data["created_at"] = parse(data["created_at"])
    return data