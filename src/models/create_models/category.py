from typing import Optional

from pydantic import BaseModel


class CreateCategory(BaseModel):
    language: str
    name: str
    description: Optional[str] = None

    # ID другой категории для которой новая категория будет дочерней и тем самым будет находиться
    # ниже по иерархии. Если не указывать, то будет категорией которая находится сразу после сервиса (главной).
    parent_id: Optional[int] = None

    # Количество кнопок для перехода в другую категорию на одну строку от 1 до 8.
    number_buttons_in_row: int = 1


class CreateCategoryTranslate(BaseModel):
    category_id: int
    lang: str
    name: str
    description: Optional[str] = None