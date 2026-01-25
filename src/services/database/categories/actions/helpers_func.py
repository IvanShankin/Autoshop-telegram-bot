import inspect as inspect_python
from datetime import datetime
from functools import lru_cache
from typing import List, Any, Callable, Awaitable, Type

import orjson
from sqlalchemy import select, inspect as sa_inspect, DateTime

from src.services.database.categories.models import CategoryFull
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis


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
    options: tuple = None,
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
            query = query.options(*options)

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
    options: tuple = None,
    join = None,
    filter_expr = None,
    order_by = None,
    post_process: Callable[[Any], Any] | None = None
) -> List[Any]:
    """
    Ищет группированные объекты, такие как: List[dict]. Ищет в redis, если нет то в БД.
    :param model_db: Модель БД которую необходимо вернуть.
    :param redis_key: Ключ для поиска по redis.
    :param join: join запрос.
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
            query = query.options(*options)
        if join is not None:
            query = query.join(join)
        if filter_expr is not None:
            query = query.where(filter_expr)
        if order_by is not None:
            query = query.order_by(order_by)

        result_db = await session_db.execute(query)
        result = result_db.scalars().unique().all()

        if result:
            await call_fun_filling()  # заполнение redis
            return [ await _maybe_await(post_process(obj)) for obj in result] if post_process else result

        return result


def _has_accounts_in_subtree(category: CategoryFull, all_categories: list[CategoryFull]) -> bool:
    """
    Проверяет, есть ли в поддереве категории хотя бы одна видимая категория-хранилище.
    Категории с show=False не учитываются и не "передают" наличие аккаунтов вверх.
    """

    # Если текущая категория скрыта — её поддерево не рассматриваем
    if not category.show:
        return False

    # Если текущая категория — хранилище и в ней есть аккаунты
    if category.is_product_storage and category.quantity_product > 0:
        return True

    # Находим дочерние категории
    children = [c for c in all_categories if c.parent_id == category.category_id]

    # Проверяем рекурсивно
    for child in children:
        if _has_accounts_in_subtree(child, all_categories):
            return True

    return False


async def get_sold_items_by_page(
        user_id: int,
        page: int,
        language: str,
        redis_key: str,
        page_size: int,
        redis_filter: Callable[[Any], bool],
        db_model: Type,
        db_filter,
        db_options: tuple,
        dto_factory: Callable[[Any], Any],
        filling_redis_func: Callable[[int], Any],
) -> List[Any]:
    """
    Универсальная функция получения проданных объектов с пагинацией через redis + db fallback
    """

    async with get_redis() as session_redis:
        result_redis = await session_redis.get(redis_key)
        if result_redis:
            objs_list: list[dict] = orjson.loads(result_redis)
            if objs_list:
                filtered = []

                for obj in objs_list:
                    dto = dto_factory(obj)
                    if redis_filter(dto):
                        filtered.append(dto)

                start = (page - 1) * page_size
                end = start + page_size
                return filtered[start:end]

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(db_model)
            .options(*db_options)
            .where(db_filter)
            .order_by(db_model.sold_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )

        await filling_redis_func(user_id)

        objs = result_db.scalars().all()

        return [dto_factory(obj) for obj in objs]