from pydantic import BaseModel
from typing import List, Dict


class AppConfig(BaseModel):
    # Типы оплаты и пополнения
    type_payments: List[str] = ['crypto_bot', 'zelenka']  # отображают в типах оплаты для админа
    min_max_replenishment: Dict[str, Dict[str, int]] = {
        'crypto_bot': {"min": 1, "max": 99999999}
    }

    # Настройки языков
    allowed_langs: List[str] = ["ru", "en"]  # все коды языков
    emoji_langs: Dict[str, str] = {
        "ru": "🇷🇺",
        "en": "🇬🇧",
    }  # эмодзи по коду языка
    name_langs: Dict[str, str] = {
        "ru": "Русский",
        "en": "English",
    }  # название языка по коду
    default_lang: str = "ru"

    # Настройки файлов
    supported_archive_extensions: List[str] = ["zip"]

    # Интерфейсные константы
    solid_line: str = '―――――――――――――――――――――――――――'  # для клавиатуры