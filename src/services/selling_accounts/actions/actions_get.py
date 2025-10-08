from datetime import datetime
from functools import lru_cache
from typing import List, Any, Callable, Awaitable
import inspect as inspect_python
import orjson

from sqlalchemy import select, inspect as sa_inspect, true, DateTime
from sqlalchemy.orm import selectinload

from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.filling_redis import (filling_type_account_services, filling_account_services, \
    filling_account_categories_by_service_id, filling_account_categories_by_category_id, \
    filling_product_accounts_by_category_id, filling_product_accounts_by_account_id, \
    filling_all_account_services, filling_sold_account_only_one_owner, \
    filling_sold_account_only_one, filling_all_types_account_service)
from src.services.database.database import get_db
from src.services.selling_accounts.models import TypeAccountServices, AccountServices, AccountCategories, \
    ProductAccounts, SoldAccounts
from src.services.selling_accounts.models.models_with_tranlslate import AccountCategoryFull, SoldAccountsFull


async def _maybe_await(v):
    try:
        if inspect_python.isawaitable(v):
            return await v
        return v
    except AttributeError: # если получили синхронную функцию
        return v

@lru_cache
def _get_model_deserializers(model_db):
    deserializers = {}
    for column in sa_inspect(model_db).columns:
        if isinstance(column.type, DateTime):
            deserializers[column.key] = lambda v: datetime.fromisoformat(v) if isinstance(v, str) else v
    return deserializers

def _deserialize_fields(model_db, data):
    deserializers = _get_model_deserializers(model_db)
    return {
        key: deserializers.get(key, lambda v: v)(value)
        for key, value in data.items()
    }

async def _get_single_obj(
    model_db,
    redis_key: str,
    filter_expr,
    call_fun_filling: Callable[[], Awaitable[None]],
    options = None,
    post_process: Callable[[Any], Any] | None = None
) -> Any | None:
    """
    Ищет один объект, такой как: dict. Ищет в redis, если нет то в БД.
    :param model_db: Модель БД которую необходимо вернуть.
    :param redis_key: Ключ для поиска по redis.
    :param filter_expr: SQLAlchemy-выражение фильтрации (например, Model.id == 123).
    :param call_fun_filling: Асинхронная функция для заполнения Redis.
    :param post_process: Асинхронная/Синхронная функция для преобразования в особый класс.
    :return: Модель БД `model_db`.
    """

    async with get_redis() as session_redis:
        result_redis = await session_redis.get(redis_key)
        if result_redis:
            model_in_dict: dict = orjson.loads(result_redis)

            # если передан post_process - он решает, что делать с dict
            if post_process:
                return await _maybe_await(post_process(model_in_dict))

            # иначе конструируем ORM модель
            return model_db(**_deserialize_fields(model_db, model_in_dict))

    async with get_db() as session_db:
        query = select(model_db)
        if options is not None:
            query = query.options(options)

        result_db = await session_db.execute(query.where(filter_expr))
        result = result_db.scalar_one_or_none()

        if result:
            await call_fun_filling()  # заполнение redis
            return await _maybe_await(post_process(result)) if post_process else result

    return None

async def _get_grouped_objects(
    model_db,
    redis_key: str,
    call_fun_filling: Callable[[], Awaitable[None]],
    options = None,
    filter_expr = None,
    order_by = None,
    post_process: Callable[[Any], Any] | None = None
) -> List[Any]:
    """
    Ищет группированные объекты, такие как: List[dict]. Ищет в redis, если нет то в БД.
    :param model_db: Модель БД которую необходимо вернуть.
    :param redis_key: Ключ для поиска по redis.
    :param filter_expr: SQLAlchemy-выражение фильтрации (например, Model.id == 123).
    :param call_fun_filling: Асинхронная функция для заполнения Redis.
    :param post_process: Асинхронная функция для преобразования в особый класс.
    :return: Список Моделей БД `List[model_db]`. Может вернуть пустой список!
    """

    async with get_redis() as session_redis:
        result_redis = await session_redis.get(redis_key)
        if result_redis:
            objs_list: list[dict] = orjson.loads(result_redis)  # список с redis
            if objs_list:
                if post_process:
                    return [await _maybe_await(post_process(obj)) for obj in objs_list]

                list_with_result = [model_db(**_deserialize_fields(model_db, obj)) for obj in objs_list]
                return list_with_result

    async with get_db() as session_db:
        query = select(model_db)
        if options is not None:
            query = query.options(options)
        if filter_expr is not None:
            query = query.where(filter_expr)
        if order_by is not None:
            query = query.order_by(order_by)

        result_db = await session_db.execute(query)
        result = result_db.scalars().all()

        if result:
            await call_fun_filling()  # заполнение redis
            return [ await _maybe_await(post_process(obj)) for obj in result] if post_process else result

        return result

async def get_all_types_account_service() -> List[TypeAccountServices] | None:
    return await _get_grouped_objects(
        model_db=TypeAccountServices,
        redis_key=f'types_account_service',
        call_fun_filling=filling_all_types_account_service
    )

async def get_type_account_service(type_account_service_id: int) -> TypeAccountServices | None:
    return await _get_single_obj(
        model_db=TypeAccountServices,
        redis_key=f'type_account_service:{type_account_service_id}',
        filter_expr=TypeAccountServices.type_account_service_id == type_account_service_id,
        call_fun_filling=filling_type_account_services
    )

async def get_all_account_services(return_not_show: bool = False) -> List[AccountServices]:
    """Вернёт отсортированный по возрастанию список AccountServices по полю index"""
    if return_not_show:
        filter_expr = true()
    else:
        filter_expr = AccountServices.show == True

    return await _get_grouped_objects(
        model_db=AccountServices,
        redis_key=f"account_services",
        filter_expr=filter_expr,
        call_fun_filling=filling_all_account_services,
        order_by=AccountServices.index.asc()
    )

async def get_account_service(account_service_id: int, return_not_show: bool = False) -> AccountServices | None:
    """
    :param account_service_id: id сервиса
    :param return_not_show: Если необходимо вернуть запись, даже если у неё стоит флаг `show = False`
    """
    service = await _get_single_obj(
        model_db=AccountServices,
        redis_key=f'account_service:{account_service_id}',
        filter_expr=AccountServices.account_service_id == account_service_id,
        call_fun_filling=filling_account_services
    )

    if return_not_show: # необходимо вернуть любую запись
        return service
    else:
        return service if service.show == True else None


async def _get_account_categories_by_service_id(
        account_service_id: int,
        language: str = 'ru',
        return_not_show: bool = False
) -> List[AccountCategoryFull]:
    """
    Вернёт не отсортированный список
    :param return_not_show: Если необходимо вернуть запись, даже если у неё стоит флаг `show = False`
    """

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return AccountCategoryFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return AccountCategoryFull.from_orm_with_translation(obj, lang=language)

    category_list: list[AccountCategories] = await _get_grouped_objects(
        model_db=AccountCategories,
        redis_key=f"account_categories_by_service_id:{account_service_id}:{language}",
        options=selectinload(AccountCategories.translations),
        filter_expr=AccountCategories.account_service_id == account_service_id,
        call_fun_filling=filling_account_categories_by_service_id,
        post_process=post_process
    )

    if return_not_show: # необходимо вернуть любую запись
        return category_list
    else:
        return_list = []
        for category in category_list:
            if category.show: return_list.append(category)

        return return_list

async def get_account_categories_by_category_id(
        account_category_id: int,
        language: str = 'ru',
        return_not_show: bool = False
) -> AccountCategoryFull | None:
    """:param return_not_show: Если необходимо вернуть запись, даже если у неё стоит флаг `show = False`"""

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return AccountCategoryFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return AccountCategoryFull.from_orm_with_translation(obj, lang=language)

    category = await _get_single_obj(
        model_db=AccountCategories,
        redis_key=f'account_categories_by_category_id:{account_category_id}:{language}',
        options=selectinload(AccountCategories.translations),
        filter_expr=AccountCategories.account_category_id == account_category_id,
        call_fun_filling=filling_account_categories_by_category_id,
        post_process=post_process
    )

    if return_not_show: # необходимо вернуть любую запись
        return category
    else:
        return category if category.show == True else None

async def get_account_categories_by_parent_id(
        account_service_id: int,
        parent_id: int = None,
        language: str = 'ru',
        return_not_show: bool = False
) -> List[AccountCategoryFull]:
    """
    Вернёт отсортированный по возрастанию список AccountCategoryFull по полю index
    :param account_service_id: id сервиса
    :param parent_id: id родителя искомых категорий, если не указывать, то вернутся категории с is_main = True
    :param language: язык
    :param return_not_show: Если необходимо вернуть запись, даже если у неё стоит флаг `show = False`
    :return:
    """
    list_category = await _get_account_categories_by_service_id(account_service_id, language, return_not_show)

    if parent_id:
        unsorted_list = [category for category in list_category if category.parent_id == parent_id]
    else:
        unsorted_list = [category for category in list_category if category.is_main == True]

    return sorted(unsorted_list, key=lambda category: category.index)

async def get_product_account_by_category_id(category_id: int) -> List[ProductAccounts]:
    return await _get_grouped_objects(
        model_db=ProductAccounts,
        redis_key=f'product_accounts_by_category_id:{category_id}',
        filter_expr=ProductAccounts.account_category_id == category_id,
        call_fun_filling=filling_product_accounts_by_category_id,
    )


async def get_product_account_by_account_id(account_id: int) -> ProductAccounts:
    return await _get_single_obj(
        model_db=ProductAccounts,
        redis_key=f'product_accounts_by_account_id:{account_id}',
        filter_expr=ProductAccounts.account_id == account_id,
        call_fun_filling=filling_product_accounts_by_account_id
    )

async def get_sold_accounts_by_owner_id(owner_id: int, language: str = 'ru') -> List[SoldAccountsFull]:
    """Отсортировано по возрастанию даты создания"""
    async def filling_list_account():
        await filling_sold_account_only_one_owner(owner_id, language)

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return SoldAccountsFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return SoldAccountsFull.from_orm_with_translation(obj, lang=language)

    return await _get_grouped_objects(
        model_db=SoldAccounts,
        redis_key=f'sold_accounts_by_owner_id:{owner_id}:{language}',
        options=selectinload(SoldAccounts.translations),
        filter_expr=SoldAccounts.owner_id == owner_id,
        order_by=SoldAccounts.created_at.desc(),
        call_fun_filling=filling_list_account,
        post_process=post_process,
    )

async def get_sold_accounts_by_account_id(sold_account_id: int, language: str = 'ru') -> SoldAccountsFull | None:

    async def filling_account():
        await filling_sold_account_only_one(sold_account_id, language)

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return SoldAccountsFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return SoldAccountsFull.from_orm_with_translation(obj, lang=language)

    return await _get_single_obj(
        model_db=SoldAccounts,
        redis_key=f'sold_accounts_by_accounts_id:{sold_account_id}:{language}',
        filter_expr=SoldAccounts.sold_account_id == sold_account_id,
        call_fun_filling=filling_account,
        options=selectinload(SoldAccounts.translations),
        post_process=post_process
    )
