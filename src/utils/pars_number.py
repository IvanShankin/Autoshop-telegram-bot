import phonenumbers

def phone_in_e164(phone: str) -> str:
    # пробуем как международный номер
    try:
        num = phonenumbers.parse(phone, None)
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    except:
        pass

    # если нет '+', пытаемся определить страну перебором всех регионов
    for region in phonenumbers.SUPPORTED_REGIONS:
        try:
            num = phonenumbers.parse(phone, region)
            if phonenumbers.is_valid_number(num):
                return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        except:
            continue

    return phone


def e164_to_pretty(phone: str) -> str | None:
    """
    Преобразует номер E.164 (+79991234567)
    в формат +7 (999) 123-45-67.
    Если регион не указан — берётся из номера автоматически.
    """
    try:
        num = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(num):
            return None

        # NATIONAL → 8 (999) 123-45-67
        national = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.NATIONAL)

        # Приводим NATIONAL к красивому виду с +<код страны>
        country_code = f"+{num.country_code}"

        # NATIONAL содержит только последнюю часть, например: 999 123-45-67
        return f"{country_code} {national}"
    except:
        return None