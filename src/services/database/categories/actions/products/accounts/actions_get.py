from typing import List, Set

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.config import get_config
from src.services.database.categories.actions.helpers_func import _get_grouped_objects, _get_single_obj, \
    get_sold_items_by_page
from src.services.database.categories.models import ProductAccounts, SoldAccounts, SoldAccountSmall, SoldAccountFull, \
    ProductAccountFull, AccountServiceType, AccountStorage, TgAccountMedia, StorageStatus
from src.services.database.core.database import get_db
from src.services.redis.filling import filling_product_account_by_account_id, filling_sold_account_by_account_id, \
    filling_sold_accounts_by_owner_id, filling_product_accounts_by_category_id


async def get_all_phone_in_account_storage(type_account_service: AccountServiceType) -> List[str]:
    """Вернёт все номера телефонов которые хранятся в БД у определённого типа сервиса"""
    async with get_db() as session_db:
        # получение данных с БД
        stmt = (
            select(AccountStorage.phone_number)
            .select_from(AccountStorage)
            .where(AccountStorage.type_account_service == type_account_service)
        )

        result = await session_db.execute(stmt)
        return result.scalars().all()


async def get_all_tg_id_in_account_storage() -> List[str]:
    """Вернёт все tg id которые хранятся в БД у телеграмм аккаунтов"""
    async with get_db() as session_db:
        # получение данных с БД
        stmt = (
            select(AccountStorage.tg_id)
            .where(AccountStorage.tg_id.is_not(None))
            .distinct()
        )

        result = await session_db.execute(stmt)
        return result.scalars().all()


async def get_product_account_by_category_id(
    category_id: int,
    get_full: bool = False
) -> List[ProductAccounts | ProductAccountFull]:
    """Вернёт только те продукты которые выставлены на продажу 'for_sale'"""
    if get_full:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                select(ProductAccounts)
                .join(ProductAccounts.account_storage)
                .options(selectinload(ProductAccounts.account_storage))
                .where(
                    (ProductAccounts.category_id == category_id) &
                    (AccountStorage.status == StorageStatus.FOR_SALE)
                )
            )
            accounts: List[ProductAccounts] = result_db.scalars().all()

            return [ProductAccountFull.from_orm_model(acc, acc.account_storage) for acc in accounts]


    return await _get_grouped_objects(
        model_db=ProductAccounts,
        redis_key=f'product_accounts_by_category:{category_id}',
        join=ProductAccounts.account_storage,
        options=(selectinload(ProductAccounts.account_storage),),
        filter_expr=(ProductAccounts.category_id == category_id) & (AccountStorage.status == StorageStatus.FOR_SALE),
        call_fun_filling=filling_product_accounts_by_category_id,
    )


async def get_product_account_by_account_id(account_id: int) -> ProductAccountFull:
    """При наличии вернёт продукт в не зависимости от статуса"""
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
        redis_key=f'product_account:{account_id}',
        options=(selectinload(ProductAccounts.account_storage), ),
        filter_expr=(ProductAccounts.account_id == account_id),
        post_process=post_process,
        call_fun_filling=call_fun_filling
    )


async def get_types_account_service_where_the_user_purchase(user_id: int) -> List[AccountServiceType]:
    result_list: List[AccountServiceType] = []

    all_account: List[SoldAccountFull] = await get_sold_accounts_by_owner_id(
        user_id,
        get_config().app.default_lang,
        get_full=True
    )
    for account in all_account:
        if not account.type_account_service in result_list:
            result_list.append(account.account_storage.type_account_service)

    return result_list


async def get_sold_accounts_by_owner_id(
    owner_id: int,
    language: str,
    get_full: bool = False
) -> List[SoldAccountSmall | SoldAccountFull]:
    """
    Вернёт все аккуанты которы не удалены

    Отсортировано по возрастанию даты создания
    """
    if get_full:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                select(SoldAccounts)
                .options(selectinload(SoldAccounts.translations), selectinload(SoldAccounts.account_storage))
                .where(
                    (SoldAccounts.owner_id == owner_id) &
                    (SoldAccounts.account_storage.has(is_active=True))
                )
                .order_by(SoldAccounts.sold_at.desc())
            )
            accounts = result_db.scalars().all()
            return [SoldAccountFull.from_orm_with_translation(acc, language) for acc in accounts]

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
        type_account_service: AccountServiceType,
        page: int,
        language: str,
        page_size: int = None
) -> List[SoldAccountSmall]:

    if page_size is None:
        page_size = get_config().different.page_size

    def dto_factory(obj) -> SoldAccountSmall:
        if isinstance(obj, dict):
            return SoldAccountSmall.model_validate(obj)

        # если пришёл ORM-объект из БД — используем существующий метод
        return SoldAccountSmall.from_orm_with_translation(obj, lang=language)


    return await get_sold_items_by_page(
        user_id=user_id,
        page=page,
        language=language,
        page_size=page_size,
        redis_key=f"sold_accounts_by_owner_id:{user_id}:{language}",
        redis_filter=lambda dto: True,
        db_model=SoldAccounts,
        db_filter=(
            (SoldAccounts.owner_id == user_id) &
            (SoldAccounts.account_storage.has(type_account_service=type_account_service)) &
            (SoldAccounts.account_storage.has(is_active=True))
        ),
        db_options=(
            selectinload(SoldAccounts.translations),
            selectinload(SoldAccounts.account_storage),
        ),
        dto_factory=dto_factory,
        filling_redis_func=filling_sold_accounts_by_owner_id
    )


async def get_count_sold_account(user_id: int, type_account_service: AccountServiceType) -> int:
    """Вернёт количество не удалённых аккаунтов"""
    async with get_db() as session_db:
        result = await session_db.execute(
            select(func.count(SoldAccounts.sold_account_id))
            .where(
                (SoldAccounts.owner_id == user_id) &
                (SoldAccounts.type_account_service == type_account_service) &
                (SoldAccounts.account_storage.has(is_active=True))
            )
        )
        return result.scalar_one()


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
        redis_key=f'sold_account:{sold_account_id}:{language}',
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


def get_type_service_account(value: str) -> AccountServiceType | None:
    """
        :return: Если тип сервиса не найден, то вернёт None
    """
    try:
        return AccountServiceType(value)
    except ValueError:
        return None

