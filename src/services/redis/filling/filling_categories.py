from typing import List

import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config import get_config
from src.services.database.categories.models import Categories
from src.services.database.categories.models.shemas.product_account_schem import CategoryFull
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis
from src.services.redis.filling.helpers_func import _filling_categories, \
    _delete_keys_by_pattern, _get_quantity_products_in_category
from src.utils.core_logger import get_logger


async def filling_main_categories():
    await _filling_categories(
        key_prefix="main_categories",
        field_condition=(Categories.is_main == True)
    )


async def filling_categories_by_parent():
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Categories)
            .where(Categories.parent_id.is_not(None))
        )
        categories: list[Categories] = result_db.scalars().all()

    for cat in categories:
        await _filling_categories(
            key_prefix=f"categories_by_parent:{cat.parent_id}",
            field_condition=(Categories.parent_id == cat.parent_id)
        )


async def filling_category_by_category(category_ids: List):
    for category_id in category_ids:
        await _delete_keys_by_pattern(f"category:{category_id}:*")

    if not category_ids:
        return

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Categories)
            .options(selectinload(Categories.translations))
            .where(Categories.category_id.in_(category_ids) )
        )
        categories: List[Categories] = result_db.scalars().all()

        if not category_ids:
            return

        async with get_redis() as session_redis:
            async with session_redis.pipeline(transaction=False) as pipe:
                for category in categories:
                    category_id = category.category_id

                    # получаем все языки которые имеются у данного объекта (obj)
                    langs = []
                    for translate in category.translations:  # получение у объекта model, его translations
                        lang = translate.lang
                        if not lang:
                            continue
                        if lang not in get_config().app.allowed_langs:
                            continue
                        if lang not in langs:
                            langs.append(lang)

                    if not langs:
                        # у объекта нет переводов — пропускаем
                        continue

                    for lang in langs:
                        try:
                            value_obj = CategoryFull.from_orm_with_translation(
                                category=category,
                                quantity_product=await _get_quantity_products_in_category(category_id),
                                lang=lang
                            )
                        except Exception as e:
                            logger = get_logger(__name__)
                            logger.warning(f"Error when converting to CategoryFull: {str(e)}")
                            continue
                        if not value_obj:
                            continue

                        value_bytes = orjson.dumps(value_obj.model_dump())
                        key = f"category:{category_id}:{lang}"
                        await pipe.set(key, value_bytes)
                await pipe.execute()


async def filling_all_keys_category(category_id: int = None):
    """Заполняет redis всеми ключами для категорий
    :param category_id: Если передать, то заполнит по всем значениям, которые связаны с ним"""
    await filling_main_categories()
    await filling_categories_by_parent()

    category_ids_for_dilling = []
    if category_id is None:
        async with get_db() as session_db:
            result = await session_db.execute(select(Categories))
            categories = result.scalars().all()
            category_ids_for_dilling = [cat.category_id for cat in categories]
    else:
        category_ids_for_dilling = [category_id]

    await filling_category_by_category(category_ids_for_dilling)

