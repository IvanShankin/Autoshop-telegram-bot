from datetime import timedelta
from typing import Type, Any, Optional, Callable, Iterable

import orjson
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.config import get_config
from src.services.database.categories.models import Categories, ProductAccounts, AccountStorage, ProductUniversal, \
    UniversalStorage, StorageStatus, CategoryFull
from src.services.database.core.database import get_db, Base
from src.services.redis.core_redis import get_redis



async def _get_quantity_products_in_category(category_id: int) -> int:
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
                (UniversalStorage.status == StorageStatus.FOR_SALE)
            )
            .scalar_subquery()

            # ПРИ ДОБАВЛЕНИЕ НОВЫХ ТОВАРОВ, РАСШИРИТЬ ПОИСК
        )

        result = await session.execute(stmt)
        return result.scalar_one()


async def _delete_keys_by_pattern(pattern: str):
    """Удаляет все ключи, соответствующие шаблону. Пример: 'user:*'"""
    count = 0
    async with get_redis() as session_redis:
        async for key in session_redis.scan_iter(match=pattern):
            await session_redis.delete(key)
            count += 1
    return count


async def _fill_redis_single_objects(
        model: Type,
        key_prefix: str,
        key_extractor: Callable[[Any], str],
        value_extractor: Callable[[Any], Any] = lambda x: orjson.dumps(x.to_dict()),
        field_condition: Optional[Any] = None,
        ttl: Optional[Callable[[Any], timedelta]] = None
):
    """
    Заполняет Redis одиночными объектами. Если объекты в БД не будут найдены, то ничего не заполнит
    :param model: модель БД
    :param key_prefix: префикс у ключа redis ("key_prefix:other_data")
    :param field_condition: условие отбора. Пример: (User.user_id == 1)
    :param key_extractor: lambda функция для вызова второй части ключа. Пример: lambda user: user.user_id
    :param value_extractor: lambda функция для метода преобразования в json строку исходное значение. Пример:  lambda x: orjson.dumps(x.to_dict())
    :param key_extractor:
    :param value_extractor:
    :param ttl:
    """
    await _delete_keys_by_pattern(f'{key_prefix}:*')
    async with get_db() as session_db:
        if field_condition:
            result_db = await session_db.execute(select(model).where(field_condition))
        else:
            result_db = await session_db.execute(select(model))

        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for obj in result:
                        key = f"{key_prefix}:{key_extractor(obj)}" # формируется ключ
                        value = value_extractor(obj)

                        if ttl:
                            if ttl(obj): # если дата есть
                                ttl_in_seconds = int(ttl(obj).total_seconds())
                                if ttl_in_seconds > 1:
                                    await pipe.setex(key, ttl_in_seconds, value)
                            else: # если даты нет, то бессрочно
                                await pipe.set(key, value)

                        else:
                            await pipe.set(key, value)
                    await pipe.execute()


async def _filling_categories(
    key_prefix: str,
    field_condition: Optional[Any] = None,
):
    """
    :param key_prefix: префикс для ключа
    :param field_condition: Условие отбора при select Categories
    """
    await _delete_keys_by_pattern(f"{key_prefix}:*")

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Categories)
            .options(selectinload(Categories.translations))
            .where(field_condition)
            .order_by(Categories.index.asc())
        )
        categories: list[Categories] = result_db.scalars().all()

        if not categories:
            return

        # union языков, которые реально есть среди объектов (и допустимы)
        langs_set = set()
        for category in categories:
            for translate in category.translations:
                lang = translate.lang
                if lang and lang in get_config().app.allowed_langs:
                    langs_set.add(lang)

        if not langs_set:
            return

        async with get_redis() as session_redis:
            async with session_redis.pipeline(transaction=False) as pipe:
                for lang in langs_set:
                    list_for_redis = []

                    for category in categories:
                        # если у объекта нет перевода для lang — пропускаем его
                        has_lang = False
                        for translate in category.translations:
                            if translate.lang == lang:
                                has_lang = True
                                break
                        if not has_lang:
                            continue

                        result_category = CategoryFull.from_orm_with_translation(
                            category = category,
                            quantity_product=await _get_quantity_products_in_category(category.category_id),
                            lang = lang
                        )

                        list_for_redis.append(result_category.model_dump())

                    if not list_for_redis:
                        continue

                    key = f"{key_prefix}:{lang}"
                    value_bytes = orjson.dumps(list_for_redis)
                    await pipe.set(key, value_bytes)
                await pipe.execute()


async def _filling_product_by_category_id(
    model_db: Type[Base],
    key_prefix: str,
    options: tuple = None,
    filter_expr: Any = None,
    join: Any = None
):
    """
    Заполнит redis по category_id. Результат - это список по category_id.

    Результат ключа: "{key_prefix}:{category_id}"
    :param model_db: любой продукт (orm объект), который имеет поле category_id
    :param key_prefix: префикс у ключа в redis
    :return:
    """
    await _delete_keys_by_pattern(f"{key_prefix}:*")  # удаляем по каждой категории

    async with get_db() as session_db:
        # Получаем все ID для группировки
        result_db = await session_db.execute(select(model_db.category_id))
        account_category_ids = result_db.scalars().all()

        for category_id in account_category_ids:
            query = select(model_db).where(model_db.category_id == category_id)
            if join is not None:
                query = query.join(join)
            if options is not None:
                query = query.options(*options)
            if filter_expr is not None:
                query = query.where(filter_expr)

            result_db = await session_db.execute(query)
            products = result_db.scalars().all()

            if products:
                async with get_redis() as session_redis:
                    list_for_redis = [obj.to_dict() for obj in products]
                    key = f"{key_prefix}:{category_id}"
                    value = orjson.dumps(list_for_redis)
                    await session_redis.set(key, value)



async def filling_sold_products_by_owner_id(
    *,
    model_db: Type,
    owner_id: int,
    key_prefix: str,
    ttl,
    options: Iterable,
    filter_expr,
    get_translations: Callable[[Any], Iterable],
    dto_factory: Callable[[Any, str], Any],
):
    """
    Универсально формирует и кэширует в Redis проданные сущности по owner_id с учётом языков.

    Redis ключ:
        {key_prefix}:{owner_id}:{lang}

    :param model_db: ORM модель (SoldUniversal / SoldAccounts)
    :param owner_id: ID владельца
    :param key_prefix: Префикс redis ключа
    :param ttl: TTL ключа
    :param options: SQLAlchemy loader options
    :param filter_expr: SQLAlchemy фильтр
    :param get_translations: Функция получения переводов из ORM объекта
    :param dto_factory: Функция преобразования ORM -> DTO по языку
    """

    await _delete_keys_by_pattern(f"{key_prefix}:{owner_id}:*")

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(model_db)
            .options(*options)
            .where(filter_expr)
            .order_by(model_db.sold_at.desc())
        )

        objects_list = result_db.scalars().unique().all()

        languages = {
            t.lang
            for obj in objects_list
            for t in get_translations(obj)
        }

        list_by_lang: list[tuple[list, str]] = []

        for lang in languages:
            new_list = [
                dto_factory(obj, lang).model_dump()
                for obj in objects_list
            ]
            list_by_lang.append((new_list, lang))

    async with get_redis() as session_redis:
        for obj_list, lang in list_by_lang:
            await session_redis.setex(
                f"{key_prefix}:{owner_id}:{lang}",
                ttl,
                orjson.dumps(obj_list)
            )


async def filling_sold_entity_by_id(
    *,
    model_db: Type,
    entity_id: int,
    key_prefix: str,
    ttl,
    options: Iterable,
    filter_expr,
    get_languages: Callable[[Any], Iterable[str]],
    dto_factory: Callable[[Any, str], Any],
):
    """
    Универсально кэширует проданную сущность по ID в Redis по всем языкам.

    Redis ключ:
        {key_prefix}:{entity_id}:{lang}

    :param model_db: ORM модель (SoldAccounts / SoldUniversal)
    :param entity_id: ID сущности
    :param key_prefix: префикс redis ключа
    :param ttl: TTL ключа
    :param options: SQLAlchemy loader options
    :param filter_expr: SQLAlchemy фильтр
    :param get_languages: функция получения языков
    :param dto_factory: ORM -> Pydantic DTO по языку
    """

    await _delete_keys_by_pattern(f"{key_prefix}:{entity_id}:*")

    async with get_db() as session_db:
        result = await session_db.execute(
            select(model_db)
            .options(*options)
            .where(filter_expr)
        )

        entity = result.scalar_one_or_none()

        if not entity:
            return

        languages = set(get_languages(entity))

        async with get_redis() as session_redis:
            for lang in languages:
                dto = dto_factory(entity, lang)

                await session_redis.setex(
                    f"{key_prefix}:{entity_id}:{lang}",
                    ttl,
                    orjson.dumps(dto.model_dump())
                )
