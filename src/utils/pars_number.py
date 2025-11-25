import phonenumbers
from phonenumbers import PhoneNumberFormat


def phone_in_e164(phone: str) -> str:
    # пробуем как международный номер
    try:
        num = phonenumbers.parse(phone, None)
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, PhoneNumberFormat.E164)
    except:
        pass

    # если нет '+', пытаемся определить страну перебором всех регионов
    for region in phonenumbers.SUPPORTED_REGIONS:
        try:
            num = phonenumbers.parse(phone, region)
            if phonenumbers.is_valid_number(num):
                return phonenumbers.format_number(num, PhoneNumberFormat.E164)
        except:
            continue

    return phone


def e164_to_pretty(phone: str) -> str | None:
    """
    Преобразует номер E.164 (+79991234567)
    в формат +7 (999) 123-45-67.
    """
    try:
        num = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(num):
            return None

        # INTERNATIONAL → "+7 999 123-45-67"
        intl = phonenumbers.format_number(num, PhoneNumberFormat.INTERNATIONAL)

        # Разбиваем: "+7 999 123-45-67"
        country, rest = intl.split(" ", 1)

        # rest = "999 123-45-67" → делаем (999) 123-45-67
        parts = rest.split(" ", 1)
        area = parts[0]              # 999
        tail = parts[1] if len(parts) > 1 else ""

        return f"{country} ({area}) {tail}"
    except:
        return None