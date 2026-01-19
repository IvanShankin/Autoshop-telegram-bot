from typing import List

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.config import get_config
from src.services.database.categories.actions.helpers_func import _get_grouped_objects, _get_single_obj, \
    get_sold_items_by_page
from src.services.database.categories.models import ProductUniversal
from src.services.database.categories.models.product_universal import UniversalStorage, SoldUniversal
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull, \
    SoldUniversalSmall, SoldUniversalFull, ProductUniversalSmall
from src.services.database.core import get_db
from src.services.redis.filling.filling_universal import filling_product_universal_by_category, \
    filling_universal_by_product_id, filling_sold_universal_by_owner_id, filling_sold_universal_by_universal_id


async def get_product_universal_by_category_id(
    category_id: int,
    get_full: bool = False,
    language: str = False,
) -> List[ProductUniversalSmall | ProductUniversalFull]:
    """
    :param get_full: При установки True вернёт ProductUniversalFull
    :param language: Только если get_full == True. Если не передать будет взять язык по умолчанию
    :return: Если get_full == False, то вернёт ProductUniversal иначе ProductUniversalFull
    """
    if get_full:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                select(ProductUniversal)
                .options(
                    selectinload(ProductUniversal.storage)
                    .selectinload(UniversalStorage.translations)
                )
                .where(ProductUniversal.category_id == category_id)
            )
            products: List[ProductUniversal] = result_db.scalars().all()

            return [ProductUniversalFull.from_orm_model(prod, language) for prod in products]

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return ProductUniversalSmall.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return ProductUniversalSmall.from_orm_model(obj)

    return await _get_grouped_objects(
        model_db=ProductUniversal,
        redis_key=f'product_universal_by_category:{category_id}',
        filter_expr=ProductUniversal.category_id == category_id,
        call_fun_filling=filling_product_universal_by_category,
        post_process=post_process
    )


async def get_product_universal_by_product_id(product_universal_id: int):
    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return ProductUniversalFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return ProductUniversalFull.from_orm_model(obj, language=get_config().app.default_lang)

    async def call_fun_filling():
        await filling_universal_by_product_id(product_universal_id)

    return await _get_single_obj(
        model_db=ProductUniversal,
        redis_key=f'product_universal:{product_universal_id}',
        options=(
            selectinload(ProductUniversal.storage)
            .selectinload(UniversalStorage.translations),
        ),
        filter_expr=ProductUniversal.product_universal_id == product_universal_id,
        post_process=post_process,
        call_fun_filling=call_fun_filling
    )


async def get_sold_universal_by_owner_id(owner_id: int, language: str) -> List[SoldUniversalSmall]:
    """
    Вернёт все товары которы не удалены

    Отсортировано по возрастанию даты создания
    """
    async def call_fun_filling():
        await filling_sold_universal_by_owner_id(owner_id)

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return SoldUniversalSmall.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return SoldUniversalSmall.from_orm_model(obj, language=language)

    return await _get_grouped_objects(
        model_db=SoldUniversal,
        redis_key=f'sold_universal_by_owner_id:{owner_id}:{language}',
        options=(
            selectinload(SoldUniversal.storage)
            .selectinload(UniversalStorage.translations),
        ),
        filter_expr=(SoldUniversal.owner_id == owner_id) & (SoldUniversal.storage.has(is_active=True)),
        order_by=SoldUniversal.sold_at.desc(),
        call_fun_filling=call_fun_filling,
        post_process=post_process,
    )


async def get_sold_universal_by_page(
        user_id: int,
        page: int,
        language: str,
        page_size: int = None
) -> List[SoldUniversalSmall]:

    if page_size is None:
        page_size = get_config().different.page_size


    def dto_factory(obj):
        if isinstance(obj, dict):
            return SoldUniversalSmall.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return SoldUniversalSmall.from_orm_model(obj, language=language)


    return await get_sold_items_by_page(
        user_id=user_id,
        page=page,
        language=language,
        page_size=page_size,
        redis_key=f"sold_universal_by_owner_id:{user_id}:{language}",
        redis_filter=lambda dto: True,  # тут нет дополнительного фильтра
        db_model=SoldUniversal,
        db_filter=(
            (SoldUniversal.owner_id == user_id) &
            (SoldUniversal.storage.has(is_active=True))
        ),
        db_options=(
            selectinload(SoldUniversal.storage)
            .selectinload(UniversalStorage.translations),
        ),
        dto_factory=dto_factory,
        filling_redis_func=filling_sold_universal_by_owner_id
    )


async def get_count_sold_universal(user_id: int)-> int:
    """Вернёт количество не удалённых аккаунтов"""
    async with get_db() as session_db:
        result = await session_db.execute(
            select(func.count(SoldUniversal.sold_universal_id))
            .join(SoldUniversal.storage)
            .where(
                (SoldUniversal.owner_id == user_id) &
                (SoldUniversal.storage.has(is_active=True))
            )
        )
        return result.scalar_one()


async def get_sold_universal_by_universal_id(sold_universal_id: int, language: str = 'ru') -> SoldUniversalFull | None:
    async def filling_account():
        await filling_sold_universal_by_universal_id(sold_universal_id)

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return SoldUniversalFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return SoldUniversalFull.from_orm_model(obj, language=language)

    return await _get_single_obj(
        model_db=SoldUniversal,
        redis_key=f'sold_universal:{sold_universal_id}:{language}',
        filter_expr=(SoldUniversal.sold_universal_id == sold_universal_id) & (SoldUniversal.storage.has(is_active=True)),
        call_fun_filling=filling_account,
        options=(
            selectinload(SoldUniversal.storage)
            .selectinload(UniversalStorage.translations),
        ),
        post_process=post_process
    )

