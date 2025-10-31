from datetime import datetime
from typing import Type
from dateutil.parser import parse
from pydantic import BaseModel


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
            elif isinstance(Expected[key], dict) and isinstance(Actual[key], dict):
                await comparison_models(Expected[key], Actual[key])
            else:
                assert Expected[key] == Actual[key],f'ключ "{key}" не совпал'


def convert_to_dict(data) -> dict:
    """Принимает BaseModel и orm модель, всю дату переведёт в одинаковый формат, даже если дата в строке"""
    if isinstance(data, BaseModel):
        data: dict = data.model_dump()
    elif not isinstance(data, dict):
        data: dict = data.to_dict()

    for key in data.keys():
        if isinstance(data[key], datetime):
            data[key] = parse(data[key])
        elif isinstance(data[key], dict):
            convert_to_dict(data[key])
        elif isinstance(data[key], str): # пытаемся преобразовать строку, возможно там дата и время
            try:
                data[key] = parse(data[key])
            except Exception:
                pass

    return data


def parse_redis_user(redis_bytes: bytes) -> dict:
    """Десериализация user из Redis с конвертацией даты"""
    import orjson
    from dateutil.parser import parse

    data = orjson.loads(redis_bytes)
    if "created_at" in data and isinstance(data["created_at"], str):
        data["created_at"] = parse(data["created_at"])
    return data