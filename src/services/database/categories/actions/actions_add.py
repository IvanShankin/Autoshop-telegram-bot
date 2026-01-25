import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.exceptions import AccountCategoryNotFound, IncorrectedNumberButton, TheCategoryStorageAccount
from src.services.database.categories.actions.actions_get import get_quantity_products_in_category
from src.services.database.categories.actions.actions_get import get_categories_by_category_id
from src.services.database.categories.models import Categories, CategoryTranslation, \
    CategoryFull
from src.services.database.core.database import get_db
from src.services.database.system.actions.actions import create_ui_image
from src.services.redis.filling import filling_main_categories, filling_categories_by_parent, \
    filling_category_by_category
from src.utils.ui_images_data import get_default_image_bytes


async def add_translation_in_category(
        category_id: int,
        language: str,
        name: str,
        description: str = None,
) -> CategoryFull:
    """
    Добавит перевод для Categories и закэширует.
    :param language: Код языка ("ru","en"...)
    :exception AccountCategoryNotFound: Если category_id не найден. Если перевод по данному языку есть
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Categories)
            .where(Categories.category_id == category_id)
        )
        category: Categories = result_db.scalar_one_or_none()

        if not category:
            raise AccountCategoryNotFound(f"Категории с id = {category_id} не найдено")

        result_db = await session_db.execute(
            select(CategoryTranslation)
            .where(
                (CategoryTranslation.category_id == category_id) &
                (CategoryTranslation.lang == language)
            )
        )
        translation: CategoryTranslation = result_db.scalar_one_or_none()
        if translation:
            raise ValueError(f"Перевод по данному языку '{language}' уже есть")

        new_translation = CategoryTranslation(
            category_id = category_id,
            lang = language,
            name = name,
            description = description,
        )
        session_db.add(new_translation)
        await session_db.commit()

        # Сбрасываем кэш, чтобы relationship подгрузился заново
        session_db.expire(category, ["translations"])

        # Перечитываем category с актуальными translations
        result_db = await session_db.execute(
            select(Categories)
            .options(selectinload(Categories.translations))
            .where(Categories.category_id == category_id)
        )
        category = result_db.scalar_one()

        full_category = CategoryFull.from_orm_with_translation(
            category=category,
            quantity_product=await get_quantity_products_in_category(category_id),
            lang=language
        )

    if full_category.is_main:
        await filling_main_categories()
    else:
        await filling_categories_by_parent()

    await filling_category_by_category([full_category.category_id])

    return full_category


async def add_category(
    language: str,
    name: str,
    description: str = None,
    parent_id: int = None,
    number_buttons_in_row: int = 1,
) -> CategoryFull:
    """
    Создаст новый Categories и закэширует его.
    :param language: Код языка ("ru","en"...)
    :param parent_id: ID другой категории для которой новая категория будет дочерней и тем самым будет находиться
    ниже по иерархии. Если не указывать, то будет категорией которая находится сразу после сервиса (главной).
    :param number_buttons_in_row: Количество кнопок для перехода в другую категорию на одну строку от 1 до 8.
    :return: Categories: только что созданный.
    :exception TheCategoryStorageAccount: Если parent_id не является хранилищем аккаунтов.
    Для задания категории как хранилище товаров, используйте метод update
    """

    if number_buttons_in_row is not None and (number_buttons_in_row < 1 or number_buttons_in_row > 8):
        raise IncorrectedNumberButton("Количество кнопок в строке, должно быть в диапазоне от 1 до 8")

    if parent_id:
        parent_category = await get_categories_by_category_id(parent_id, return_not_show=True)
        if not parent_category:
            raise AccountCategoryNotFound()
        if parent_category.is_product_storage:
            raise TheCategoryStorageAccount(
                f"Родительский аккаунт (parent_id = {parent_id}) является хранилищем товаров. "
                f"К данной категории нельзя прикрепить другую категорию"
            )

    async with get_db() as session_db:
        if parent_id:
            is_main = False
            result_db = await session_db.execute(
                select(Categories)
                .where(Categories.parent_id == parent_id)
            )

        else:
            is_main = True
            result_db = await session_db.execute(
                select(Categories)
                .where(Categories.is_main == True)
            )

        categories = result_db.scalars().all()
        new_index = max((category.index for category in categories), default=-1) + 1

        # создание простой фото заглушки с белым фоном
        file_data = get_default_image_bytes()
        key = str(uuid.uuid4())
        new_ui_image = await create_ui_image(key=key, file_data=file_data, show=False)

        # создание категории
        new_account_categories = Categories(
            parent_id = parent_id,
            ui_image_key = new_ui_image.key,
            index = new_index,
            number_buttons_in_row = number_buttons_in_row,
            is_main = is_main,
        )
        session_db.add(new_account_categories)
        await session_db.commit()
        await session_db.refresh(new_account_categories)

    return await add_translation_in_category(
        category_id = new_account_categories.category_id,
        language = language,
        name = name,
        description = description
    )

