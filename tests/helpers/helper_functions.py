import logging
from datetime import datetime
from typing import Type, Any, Dict

from dateutil.parser import parse
from orjson import orjson
from pydantic import BaseModel

from src.database import Base


def _get_dict(obj: Any) -> Dict:
    if isinstance(obj, dict): return obj
    if isinstance(obj, bytes): return orjson.loads(obj)
    if isinstance(obj, BaseModel): return obj.model_dump()
    elif isinstance(obj, Base): return obj.to_dict()
    else: raise RuntimeError(f"невалидный формат у: {obj}")


def comparison_models(Expected: Type | dict, Actual: Type | dict, keys_not_checked: list = []):
    """Сравнивает две модели БД"""
    Expected = _get_dict(Expected)
    Actual = _get_dict(Actual)

    if not Actual:
        return False

    for key in Expected.keys():
        if not key in keys_not_checked:
            # если ожидаемый результат должен быть датой, и актуальный является не датой
            if isinstance(Expected[key], datetime) and not isinstance(Actual[key], datetime):
                assert Expected[key] == parse(Actual[key])
            elif isinstance(Expected[key], dict) and isinstance(Actual[key], dict):
                comparison_models(Expected[key], Actual[key])
            else:
                if not Expected[key] == Actual[key]:
                    logging.getLogger("comparison_models").info(f"ключ '{key}' не совпал")
                    return False

        return True


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