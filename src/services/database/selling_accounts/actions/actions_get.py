from datetime import datetime
from functools import lru_cache
from typing import List, Any, Callable, Awaitable, Set
import inspect as inspect_python
import orjson

from sqlalchemy import select, inspect as sa_inspect, true, DateTime, func
from sqlalchemy.orm import selectinload

from src.config import PAGE_SIZE, DEFAULT_LANG
from src.services.database.selling_accounts.models.models import AccountStorage, TgAccountMedia
from src.services.redis.core_redis import get_redis
from src.services.redis.filling_redis import (
    filling_type_account_services, filling_account_services, filling_account_categories_by_service_id,
    filling_account_categories_by_category_id, filling_product_accounts_by_category_id, filling_product_account_by_account_id,
    filling_all_account_services, filling_sold_account_by_account_id, filling_all_types_account_service,
    filling_sold_accounts_by_owner_id
)
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.models import TypeAccountServices, AccountServices, AccountCategories, \
    ProductAccounts, SoldAccounts, AccountCategoryFull, SoldAccountSmall, SoldAccountFull, \
    ProductAccountFull


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
            query = query.options(*options)
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


def _has_accounts_in_subtree(category: AccountCategoryFull, all_categories: list[AccountCategoryFull]) -> bool:
    """
    Проверяет, есть ли в поддереве категории хотя бы одна видимая категория-хранилище с аккаунтами.
    Категории с show=False не учитываются и не "передают" наличие аккаунтов вверх.
    """

    # Если текущая категория скрыта — её поддерево не рассматриваем
    if not category.show:
        return False

    # Если текущая категория — хранилище и в ней есть аккаунты
    if category.is_accounts_storage and category.quantity_product_account > 0:
        return True

    # Находим дочерние категории
    children = [c for c in all_categories if c.parent_id == category.account_category_id]

    # Проверяем рекурсивно
    for child in children:
        if _has_accounts_in_subtree(child, all_categories):
            return True

    return False

async def _get_account_categories_by_service_id(
        account_service_id: int,
        language: str = 'ru',
        return_not_show: bool = False
) -> List[AccountCategoryFull]:
    """
    Вернёт не отсортированный список
    :param return_not_show: Если необходимо вернуть запись, даже если у неё стоит флаг `show = False`
    """

    def post_process(obj: AccountCategories | dict):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return AccountCategoryFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return AccountCategoryFull.from_orm_with_translation(
            obj,
            lang=language,
            quantity_product_account=len(obj.product_accounts)
        )

    category_list: list[AccountCategories] = await _get_grouped_objects(
        model_db=AccountCategories,
        redis_key=f"account_categories_by_service_id:{account_service_id}:{language}",
        options=(selectinload(AccountCategories.translations), selectinload(AccountCategories.product_accounts)),
        filter_expr=AccountCategories.account_service_id == account_service_id,
        call_fun_filling=filling_account_categories_by_service_id,
        post_process=post_process
    )

    if return_not_show: # необходимо вернуть любую запись
        return category_list

    # Фильтрация по show и наличию аккаунтов в поддереве
    return [
        category for category in category_list
        if category.show and _has_accounts_in_subtree(category, category_list)
    ]

async def get_account_categories_by_category_id(
        account_category_id: int,
        language: str = 'ru',
        return_not_show: bool = False
) -> AccountCategoryFull | None:
    """:param return_not_show: Если необходимо вернуть запись, даже если у неё стоит флаг `show = False`"""

    def post_process(obj: AccountCategories | dict):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return AccountCategoryFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return AccountCategoryFull.from_orm_with_translation(
            obj,
            quantity_product_account=len(obj.product_accounts),
            lang=language
        )

    category = await _get_single_obj(
        model_db=AccountCategories,
        redis_key=f'account_categories_by_category_id:{account_category_id}:{language}',
        options=(selectinload(AccountCategories.translations), selectinload(AccountCategories.product_accounts)),
        filter_expr=AccountCategories.account_category_id == account_category_id,
        call_fun_filling=filling_account_categories_by_category_id,
        post_process=post_process
    )

    if return_not_show: # необходимо вернуть любую запись
        return category
    else:
        return category if category and category.show == True else None


async def get_all_phone_in_account_storage(type_account_service_id: int) -> Set[str]:
    """Вернёт все номера телефонов которые хранятся в БД у определённого типа сервиса"""
    async with get_db() as session_db:
        # получение данных с БД
        stmt = (
            select(AccountStorage.phone_number)
            .select_from(AccountStorage)
            .join(ProductAccounts, ProductAccounts.account_storage_id == AccountStorage.account_storage_id)
            .where(ProductAccounts.type_account_service_id == type_account_service_id)
        ).union(
            select(AccountStorage.phone_number)
            .select_from(AccountStorage)
            .join(SoldAccounts, SoldAccounts.account_storage_id == AccountStorage.account_storage_id)
            .where(SoldAccounts.type_account_service_id == type_account_service_id)
        )

        result = await session_db.execute(stmt)
        return (result.scalars().all())


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

async def get_product_account_by_category_id(
    category_id: int,
    get_full: bool = False
) -> List[ProductAccounts | ProductAccountFull]:
    if get_full:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                select(ProductAccounts)
                .options(selectinload(ProductAccounts.account_storage))
                .where(ProductAccounts.account_category_id == category_id)
            )
            accounts: List[ProductAccounts] = result_db.scalars().all()

            return [ProductAccountFull.from_orm_model(acc, acc.account_storage) for acc in accounts]


    return await _get_grouped_objects(
        model_db=ProductAccounts,
        redis_key=f'product_accounts_by_category_id:{category_id}',
        filter_expr=ProductAccounts.account_category_id == category_id,
        call_fun_filling=filling_product_accounts_by_category_id,
    )


async def get_product_account_by_account_id(account_id: int) -> ProductAccountFull:
    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return ProductAccountFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return ProductAccountFull.from_orm_model(obj, obj.account_storage)

    async def call_fun_filling():
        await filling_product_account_by_account_id(account_id)

    return await _get_single_obj(
        model_db=ProductAccounts,
        redis_key=f'product_accounts_by_account_id:{account_id}',
        options=(selectinload(ProductAccounts.account_storage), ),
        filter_expr=ProductAccounts.account_id == account_id,
        post_process=post_process,
        call_fun_filling=call_fun_filling
    )

async def get_sold_accounts_by_owner_id(owner_id: int, language: str) -> List[SoldAccountSmall]:
    """
    Вернёт все аккуанты которы не удалены

    Отсортировано по возрастанию даты создания
    """
    async def filling_list_account():
        await filling_sold_accounts_by_owner_id(owner_id)

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return SoldAccountSmall.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return SoldAccountSmall.from_orm_with_translation(obj, lang=language)

    return await _get_grouped_objects(
        model_db=SoldAccounts,
        redis_key=f'sold_accounts_by_owner_id:{owner_id}:{language}',
        options=(selectinload(SoldAccounts.translations), selectinload(SoldAccounts.account_storage)),
        filter_expr=(SoldAccounts.owner_id == owner_id) & (SoldAccounts.account_storage.has(is_active=True)),
        order_by=SoldAccounts.sold_at.desc(),
        call_fun_filling=filling_list_account,
        post_process=post_process,
    )

async def get_sold_account_by_page(
        user_id: int,
        type_account_service_id: int,
        page: int,
        language: str,
        page_size: int = PAGE_SIZE
) -> List[SoldAccountSmall]:
    """
        Возвращает список проданных аккаунтов пользователя с пагинацией. Не вернёт удалённые аккаунты
        Отсортировано по дате продажи (desc).
    """
    async with get_redis() as session_redis:
        result_redis = await session_redis.get(f'sold_accounts_by_owner_id:{user_id}:{language}')
        if result_redis:
            objs_list: list[dict] = orjson.loads(result_redis)  # список с redis
            if objs_list:
                account_list = []
                for account in objs_list:
                    account_validate = SoldAccountSmall.model_validate(account)
                    if account_validate.type_account_service_id == type_account_service_id:
                        account_list.append(account_validate)

                start = (page - 1) * page_size
                end = start + page_size
                return account_list[start:end]

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(SoldAccounts)
            .options(selectinload(SoldAccounts.translations), selectinload(SoldAccounts.account_storage))
            .where(
                (SoldAccounts.owner_id == user_id) &
                (SoldAccounts.type_account_service_id == type_account_service_id) &
                (SoldAccounts.account_storage.has(is_active=True))
            )
            .order_by(SoldAccounts.sold_at.desc())
            .limit(page_size).offset((page - 1) * page_size)
        )
        await filling_sold_accounts_by_owner_id(user_id)
        account_list = result_db.scalars().all()

        return [SoldAccountSmall.from_orm_with_translation(account, lang=language) for account in account_list]

async def get_count_sold_account(user_id: int, type_account_service_id: int) -> int:
    """Вернёт количество не удалённых аккаунтов"""
    async with get_db() as session_db:
        result = await session_db.execute(
            select(func.count(SoldAccounts.sold_account_id))
            .where(
                (SoldAccounts.owner_id == user_id) &
                (SoldAccounts.type_account_service_id == type_account_service_id) &
                (SoldAccounts.account_storage.has(is_active=True))
            )
        )
        return result.scalar_one()


async def get_union_type_account_service_id(user_id: int) -> List[int]:
    async with get_redis() as session_redis:
        result_redis = await session_redis.get(f'sold_accounts_by_owner_id:{user_id}:{DEFAULT_LANG}')
        if result_redis:
            objs_list: list[dict] = orjson.loads(result_redis)  # список с redis
            if objs_list:
                type_ids = []
                for account in objs_list:
                    account_validate = SoldAccountSmall.model_validate(account)
                    if account_validate.type_account_service_id not in type_ids:
                        type_ids.append(account_validate.type_account_service_id)

                return type_ids

    async with get_db() as session_db:
        result = await session_db.execute(
            select(SoldAccounts.type_account_service_id)
            .where(
                (SoldAccounts.owner_id == user_id)
                & (SoldAccounts.account_storage.has(is_active=True))
            )
            .distinct()  # выбираем только уникальные значения
        )
        await filling_sold_accounts_by_owner_id(user_id)
        return [row[0] for row in result.all()]


async def get_sold_accounts_by_account_id(sold_account_id: int, language: str = 'ru') -> SoldAccountFull | None:
    async def filling_account():
        await filling_sold_account_by_account_id(sold_account_id)

    def post_process(obj):
        # если пришёл словарь (из кеша), создаём DTO напрямую
        if isinstance(obj, dict):
            return SoldAccountFull.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return SoldAccountFull.from_orm_with_translation(obj, lang=language)

    return await _get_single_obj(
        model_db=SoldAccounts,
        redis_key=f'sold_accounts_by_accounts_id:{sold_account_id}:{language}',
        filter_expr=(SoldAccounts.sold_account_id == sold_account_id) & (SoldAccounts.account_storage.has(is_active=True)),
        call_fun_filling=filling_account,
        options=(selectinload(SoldAccounts.translations), selectinload(SoldAccounts.account_storage)),
        post_process=post_process
    )

async def get_account_storage(account_storage_id: int) -> AccountStorage | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(AccountStorage).where(AccountStorage.account_storage_id == account_storage_id))
        return result_db.scalar_one_or_none()


async def get_tg_account_media(account_storage_id: int) -> TgAccountMedia:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TgAccountMedia).where(TgAccountMedia.account_storage_id == account_storage_id))
        return result_db.scalar_one_or_none()
