from typing import List

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.config import get_config
from src.services.database.categories.actions.helpers_func import _has_accounts_in_subtree, _get_grouped_objects, \
    _get_single_obj
from src.services.database.categories.actions.products.accounts.actions_get import get_sold_accounts_by_owner_id
from src.services.database.categories.actions.products.universal.actions_get import get_sold_universal_by_owner_id
from src.services.database.categories.models import Categories, CategoryFull, ProductUniversal, AccountStorage, \
    ProductAccounts, CategoryTranslation
from src.services.database.categories.models.main_category_and_product import ProductType, Purchases
from src.services.database.categories.models.product_universal import UniversalStorage, UniversalStorageStatus
from src.services.database.core import get_db
from src.services.redis.filling import (
    filling_category_by_category,
    filling_categories_by_parent, filling_main_categories
)


async def get_all_translations_category(category_id: int) -> List[CategoryTranslation]:
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(CategoryTranslation)
            .where(CategoryTranslation.category_id == category_id)
        )
        return result_db.scalars().all()


async def get_category_by_category_id(
    category_id: int,
    language: str = 'ru',
    return_not_show: bool = False
) -> CategoryFull | None:
    """:param return_not_show: Если необходимо вернуть запись, даже если у неё стоит флаг `show = False`"""

    async def post_process(obj: Categories | dict):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return CategoryFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return CategoryFull.from_orm_with_translation(
            obj,
            quantity_product=await get_quantity_products_in_category(obj.category_id),
            lang=language
        )

    async def call_fun_filling():
        await filling_category_by_category([category_id])

    category = await _get_single_obj(
        model_db=Categories,
        redis_key=f'category:{category_id}:{language}',
        options=(selectinload(Categories.translations), ),
        filter_expr=Categories.category_id == category_id,
        call_fun_filling=call_fun_filling,
        post_process=post_process
    )

    if return_not_show: # необходимо вернуть любую запись
        return category
    else:
        return category if category and category.show == True else None


async def get_categories(
        parent_id: int = None,
        language: str = 'ru',
        return_not_show: bool = False
) -> List[CategoryFull]:
    """
        Вернёт отсортированный по возрастанию список CategoryFull по полю index
        :param parent_id: id родителя искомых категорий, если не указывать, то вернутся категории с is_main = True
        :param language: язык
        :param return_not_show: Если необходимо вернуть запись, даже если у неё стоит флаг `show = False`
        :return:
    """

    async def post_process(obj: Categories | dict):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return CategoryFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return CategoryFull.from_orm_with_translation(
            obj,
            lang=language,
            quantity_product=await get_quantity_products_in_category(obj.category_id)
        )

    category_list: list[Categories] = await _get_grouped_objects(
        model_db=Categories,
        redis_key=f"categories_by_parent:{parent_id}:{language}" if parent_id else f"main_categories:{language}",
        options=(selectinload(Categories.translations), ),
        filter_expr=Categories.parent_id == parent_id if parent_id else Categories.is_main == True,
        call_fun_filling=filling_categories_by_parent if parent_id else filling_main_categories,
        post_process=post_process
    )

    if return_not_show:
        sorted_list = category_list
    else:
        # Фильтрация по show и наличию товара в поддереве
        sorted_list = [
            category for category in category_list
            if category.show and _has_accounts_in_subtree(category, category_list)
        ]

    return sorted(sorted_list, key=lambda category: category.index)


async def get_types_product_where_the_user_has_product(user_id: int) -> List[ProductType]:
    result_list: List[ProductType] = []

    if await get_sold_accounts_by_owner_id(user_id, get_config().app.default_lang):
        result_list.append(ProductType.ACCOUNT)

    if await get_sold_universal_by_owner_id(user_id, get_config().app.default_lang):
        result_list.append(ProductType.UNIVERSAL)

    # ПРИ ДОБАВЛЕНИЕ НОВЫХ ТОВАРОВ, РАСШИРИТЬ ПОИСК

    return result_list


async def get_quantity_products_in_category(category_id: int) -> int:
    async with get_db() as session:
        stmt = select(
            select(func.count())
            .select_from(ProductAccounts)
            .join(ProductAccounts.account_storage)
            .where(
                (ProductAccounts.category_id == category_id) &
                (AccountStorage.status == "for_sale")
            )
            .scalar_subquery()
            +
            select(func.count())
            .select_from(ProductUniversal)
            .join(ProductUniversal.storage)
            .where(
                (ProductUniversal.category_id == category_id) &
                (UniversalStorage.status == UniversalStorageStatus.FOR_SALE)
            )
            .scalar_subquery()

            # ПРИ ДОБАВЛЕНИЕ НОВЫХ ТОВАРОВ, РАСШИРИТЬ ПОИСК
        )

        result = await session.execute(stmt)
        return result.scalar_one()


async def get_purchases(purchase_id: int) -> Purchases | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(Purchases).where(Purchases.purchase_id == purchase_id))
        return result_db.scalar_one_or_none()