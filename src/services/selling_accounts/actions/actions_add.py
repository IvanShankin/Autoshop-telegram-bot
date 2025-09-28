import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.redis_dependencies.core_redis import get_redis
from src.services.database.database import get_db
from src.services.selling_accounts.actions.actions_get import get_account_service, \
    get_account_categories_by_category_id, _get_account_categories_by_service_id, get_type_account_service, \
    get_product_account_by_category_id, get_sold_accounts_by_owner_id
from src.services.selling_accounts.models import AccountServices, AccountCategories, AccountCategoryTranslation, \
    ProductAccounts, SoldAccounts, SoldAccountsTranslation, DeletedAccounts
from src.services.selling_accounts.models.models_with_tranlslate import AccountCategoryFull, SoldAccountsFull
from src.services.users.actions import get_user


async def add_account_services(name: str, type_account_service_id: int) -> AccountServices:
    """
    У одного типа сервиса может быть только один прикреплённый сервис,
    то есть не должно быть такого, что есть два telegram или два instagram (на other не распространяется)

    Будет установлен самый большой индекс + 1
    :return AccountServices: только что созданный
    :exception ValueError: Если данный тип сервиса занят
    """

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountServices)
            .where(AccountServices.type_account_service_id == type_account_service_id)
        )

        account_service = result_db.scalar_one_or_none()
        if account_service:
            if not account_service.name == "other":
                raise ValueError("Данный тип сервиса занят")

        result_db = await session_db.execute(select(AccountServices).order_by(AccountServices.index.asc()))
        all_services: list[AccountServices] = result_db.scalars().all() # тут уже отсортированный по index

        new_index = max((service.index for service in all_services), default=-1) + 1

        new_account_service = AccountServices(
            name=name,
            index=new_index,
            show=True,
            type_account_service_id=type_account_service_id,
        )
        session_db.add(new_account_service)
        await session_db.commit()
        await session_db.refresh(new_account_service)
        all_services.append(new_account_service)

    async with get_redis() as session_redis:
        list_for_redis = [service.to_dict() for service in all_services]

        await session_redis.set(
            f"account_services",
            orjson.dumps(list_for_redis)
        )
        await session_redis.set(
            f"account_service:{new_account_service.account_service_id}",
            orjson.dumps(new_account_service.to_dict())
        )

    return new_account_service

async def add_translation_in_account_category(
        account_category_id: int,
        language: str,
        name: str,
        description: str = None,
) -> AccountCategoryFull:
    """
    Добавит перевод для AccountCategories и закэширует.
    :exception ValueError: Если account_category_id не найден. Если перевод по данному языку есть
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountCategories)
            .where(AccountCategories.account_category_id == account_category_id)
        )
        category: AccountCategories = result_db.scalar_one_or_none()

        if not category:
            raise ValueError(f"Категории с id = {account_category_id} не найдено")

        result_db = await session_db.execute(
            select(AccountCategoryTranslation)
            .where(
                (AccountCategoryTranslation.account_category_id == account_category_id) &
                (AccountCategoryTranslation.lang == language)
            )
        )
        translation: AccountCategoryTranslation = result_db.scalar_one_or_none()
        if translation:
            raise ValueError(f"Перевод по данному языку '{language}' уже есть")

        new_translation = AccountCategoryTranslation(
            account_category_id = account_category_id,
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
            select(AccountCategories)
            .options(selectinload(AccountCategories.translations))
            .where(AccountCategories.account_category_id == account_category_id)
        )
        category = result_db.scalar_one()

        full_category = AccountCategoryFull.from_orm_with_translation(category, language)

    new_all_categories = [full_category.model_dump()]
    all_categories = await _get_account_categories_by_service_id(full_category.account_service_id)
    for category in all_categories:
        new_all_categories.append(category.model_dump())

    async with get_redis() as session_redis:
        await session_redis.set(
            f"account_categories_by_service_id:{full_category.account_service_id}:{language}",
            orjson.dumps(new_all_categories)
        )
        await session_redis.set(
            f"account_categories_by_category_id:{account_category_id}:{language}",
            orjson.dumps(full_category.model_dump())
        )

    return full_category

async def add_account_category(
        account_service_id: int,
        language: str,
        name: str,
        description: str = None,
        parent_id: int = None,
        is_accounts_storage: bool = False,
        price_one_account: int = None,
        cost_price_one_account: int = None
) -> AccountCategoryFull:
    """
    Создаст новый AccountCategories и закэширует его.
    :param account_service_id: Сервис у данной категории.
    :param parent_id: ID другой категории для которой новая категория будет дочерней и тем самым будет находиться
    ниже по иерархии. Если не указывать, то будет категорией которая находится сразу после сервиса.
    :param is_accounts_storage: Флаг установки категории хранилищем аккаунтов.
    :param price_one_account: Цена одного аккаунта.
    :param cost_price_one_account: Себестоимость аккаунта.
    :return: AccountCategories: только что созданный
    :exception ValueError: Если account_service_id не найден.
    """

    if price_one_account is not None and price_one_account <= 0:
        raise ValueError("Цена аккаунтов должна быть положительным числом")
    if cost_price_one_account is not None and cost_price_one_account < 0:
        raise ValueError("Себестоимость аккаунтов должна быть положительным числом")

    if not await get_account_service(account_service_id, return_not_show=True):
        raise ValueError(f"Сервис для аккаунтов с id = {account_service_id} не найдена")

    if parent_id:
        parent_category = await get_account_categories_by_category_id(parent_id, return_not_show=True)
        if parent_category.is_accounts_storage:
            raise ValueError(
                f"Родительский аккаунт (parent_id = {parent_id}) является хранилищем аккаунтов. "
                f"К данной категории нельзя прикрепить другую категорию"
            )

    async with get_db() as session_db:
        if parent_id:
            is_main = False
            result_db = await session_db.execute(
                select(AccountCategories)
                .where(AccountCategories.parent_id == parent_id)
            )

        else:
            is_main = True
            result_db = await session_db.execute(
                select(AccountCategories)
                .where(AccountCategories.is_main == True)
            )

        categories = result_db.scalars().all()
        new_index = max((category.index for category in categories), default=-1) + 1

        new_account_categories = AccountCategories(
            account_service_id = account_service_id,
            parent_id = parent_id,
            index = new_index,
            is_main = is_main,
            is_accounts_storage = is_accounts_storage,

            # только для тех категорий которые хранят аккаунты (is_accounts_storage == True)
            price_one_account = price_one_account,
            cost_price_one_account = cost_price_one_account
        )
        session_db.add(new_account_categories)
        await session_db.commit()
        await session_db.refresh(new_account_categories)

    return await add_translation_in_account_category(
        account_category_id = new_account_categories.account_category_id,
        language = language,
        name = name,
        description = description
    )


async def add_product_account(
        account_category_id: int,
        hash_login: str = None,
        hash_password: str = None
) -> ProductAccounts:
    """
    Добавится аккаунт в категорию только где is_accounts_storage = True.
    У аккаунта будет присвоен тип сервиса такой же как у категории
    """

    category = await get_account_categories_by_category_id(account_category_id, return_not_show=True)
    if not category:
        raise ValueError(f"Категория аккаунтов с id = {account_category_id} не найдена")
    elif not category.is_accounts_storage:
        raise ValueError(
            f"Категория аккаунтов с id = {account_category_id} не является хранилищем аккаунтов. "
            f"для добавления аккаунтов необходимо сделать хранилищем"
        )

    service = await get_account_service(category.account_service_id, return_not_show=True)
    new_product_account = ProductAccounts(
        type_account_service_id = service.type_account_service_id,
        account_category_id = account_category_id,
        hash_login = hash_login,
        hash_password = hash_password
    )

    async with get_db() as session_db:
        session_db.add(new_product_account)
        await session_db.commit()
        await session_db.refresh(new_product_account)

    all_account = await get_product_account_by_category_id(account_category_id)
    new_list_accounts = [new_product_account.to_dict()]
    for account in all_account:
        new_list_accounts.append(account.to_dict())

    async with get_redis() as session_redis:
        await session_redis.set(
            f"product_accounts_by_category_id:{account_category_id}",
            orjson.dumps(new_list_accounts)
        )
        await session_redis.set(
            f"product_accounts_by_account_id:{new_product_account.account_id}",
            orjson.dumps(new_product_account.to_dict())
        )

    return new_product_account


async def add_translation_in_sold_account(
    sold_account_id: int,
    language: str,
    name: str,
    description: str
) -> SoldAccountsFull:
    """Добавит перевод и закэширует"""

    async with get_db() as session_db:
        result_db = await session_db.execute(select(SoldAccounts).where(SoldAccounts.sold_account_id == sold_account_id))
        sold_account = result_db.scalar_one_or_none()
        if not sold_account:
            raise ValueError(f"Продаваемый аккаунт с ID = {sold_account_id} не найден")

        result_db = await session_db.execute(
            select(SoldAccountsTranslation)
            .where(
                (SoldAccountsTranslation.sold_account_id == sold_account_id) &
                (SoldAccountsTranslation.lang == language)
            )
        )
        translation = result_db.scalar_one_or_none()
        if translation:
            raise ValueError(f"Перевод по данному языку '{language}' уже есть")

        new_translation = SoldAccountsTranslation(
            sold_account_id = sold_account_id,
            lang = language,
            name = name,
            description = description
        )
        session_db.add(new_translation)
        await session_db.commit()

        # Сбрасываем кэш, чтобы relationship подгрузился заново
        session_db.expire(sold_account, ["translations"])
        result_db = await session_db.execute(
            select(SoldAccounts)
            .options(selectinload(SoldAccounts.translations))
            .where(SoldAccounts.sold_account_id == sold_account_id)
        )
        sold_account = result_db.scalar_one_or_none()

        full_sold_account = SoldAccountsFull.from_orm_with_translation(sold_account, language)

    all_account = await get_sold_accounts_by_owner_id(full_sold_account.owner_id)
    all_account.append(full_sold_account)
    all_account = [account.model_dump() for account in all_account]

    async with get_redis() as session_redis:
        await session_redis.set(
            f"sold_accounts_by_owner_id:{full_sold_account.owner_id}:{language}",
            orjson.dumps(all_account)
        )
        await session_redis.set(
            f"sold_accounts_by_accounts_id:{sold_account_id}:{language}",
            orjson.dumps(full_sold_account.model_dump())
        )

    return full_sold_account


async def add_sold_sold_account(
    owner_id: int,
    type_account_service_id: int,
    is_valid: bool,
    is_deleted: bool,
    language: str,
    name: str,
    description: str,
    hash_login: str = None,
    hash_password: str = None,
) -> SoldAccountsFull:
    """Сделает запись в БД, и закэширует"""
    if not await get_user(owner_id):
        raise ValueError(f"Пользователь с ID = {owner_id} не найден")

    if not await get_type_account_service(type_account_service_id):
        raise ValueError(f"Тип сервиса с ID = {type_account_service_id} не найден")

    new_sold_account = SoldAccounts(
        owner_id = owner_id,
        type_account_service_id = type_account_service_id,
        is_valid = is_valid,
        is_deleted = is_deleted,
        hash_login = hash_login,
        hash_password = hash_password
    )

    async with get_db() as session_db:
        session_db.add(new_sold_account)
        await session_db.commit()
        await session_db.refresh(new_sold_account)

    return await add_translation_in_sold_account(
        sold_account_id=new_sold_account.sold_account_id,
        language=language,
        name=name,
        description=description
    )

async def add_deleted_accounts(
        type_account_service_id: int,
        category_name: str,
        description: str
) -> DeletedAccounts:

    if not await get_type_account_service(type_account_service_id):
        raise ValueError(f"Тип сервиса с id = {type_account_service_id} не найден")

    async with get_db() as session_db:
        new_deleted_account = DeletedAccounts(
            type_account_service_id = type_account_service_id,
            category_name = category_name,
            description = description
        )

        session_db.add(new_deleted_account)
        await session_db.commit()
        await session_db.refresh(new_deleted_account)

    return new_deleted_account