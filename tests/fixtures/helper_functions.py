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
            if isinstance(Expected[key], datetime):
                assert Expected[key] == parse(Actual[key])
            else:
                assert Expected[key] == Actual[key],f'ключ "{key}" не совпал'