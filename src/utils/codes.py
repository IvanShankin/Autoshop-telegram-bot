import random
import string


def generate_code(length=7):
    # Все возможные символы для кода (буквы и цифры)
    characters = string.ascii_uppercase + string.digits
    # Генерируем случайную строку
    return ''.join(random.choice(characters) for _ in range(length))