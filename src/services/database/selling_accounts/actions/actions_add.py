import uuid
from pathlib import Path
from typing import Literal

import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config import TYPE_ACCOUNT_SERVICES
from src.exceptions.service_exceptions import TranslationAlreadyExists, ServiceTypeBusy, AccountServiceNotFound, \
    AccountCategoryNotFound, IncorrectedNumberButton, IncorrectedAmountSale, IncorrectedCostPrice, \
    TheCategoryStorageAccount, CategoryNotFound, TheCategoryNotStorageAccount
from src.services.database.selling_accounts.models import AccountStorage
from src.services.database.selling_accounts.models.models import TgAccountMedia
from src.services.database.system.actions.actions import create_ui_image
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.actions.actions_get import get_account_service, \
    get_account_categories_by_category_id, _get_account_categories_by_service_id, get_type_account_service, \
    get_product_account_by_category_id
from src.services.database.selling_accounts.models import AccountServices, AccountCategories, AccountCategoryTranslation, \
    ProductAccounts, SoldAccounts, SoldAccountsTranslation, DeletedAccounts, AccountCategoryFull, SoldAccountSmall
from src.services.database.users.actions import get_user
from src.services.redis.filling_redis import filling_product_account_by_account_id, \
    filling_product_accounts_by_category_id, filling_sold_accounts_by_owner_id, filling_sold_account_by_account_id, \
    filling_account_categories_by_service_id, filling_account_categories_by_category_id
from src.utils.pars_number import phone_in_e164
from src.utils.ui_images_data import get_default_image_bytes


async def add_account_services(name: str, type_account_service_id: int) -> AccountServices:
    """
    У одного типа сервиса может быть только один прикреплённый сервис,
    то есть не должно быть такого, что есть два telegram или два instagram (на other не распространяется)

    Будет установлен самый большой индекс + 1
    :return AccountServices: только что созданный
    :exception ServiceTypeBusy: Если данный тип сервиса занят
    """

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountServices)
            .where(AccountServices.type_account_service_id == type_account_service_id)
        )

        account_service = result_db.scalar_one_or_none()
        if account_service:
            if not account_service.name == "other":
                raise ServiceTypeBusy("Данный тип сервиса занят")

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
    :param language: Код языка ("ru","en"...)
    :exception AccountCategoryNotFound: Если account_category_id не найден. Если перевод по данному языку есть
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountCategories)
            .where(AccountCategories.account_category_id == account_category_id)
        )
        category: AccountCategories = result_db.scalar_one_or_none()

        if not category:
            raise AccountCategoryNotFound(f"Категории с id = {account_category_id} не найдено")

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
            .options(
                selectinload(AccountCategories.translations),
                selectinload(AccountCategories.product_accounts)
            )
            .where(AccountCategories.account_category_id == account_category_id)
        )
        category = result_db.scalar_one()

        full_category = AccountCategoryFull.from_orm_with_translation(
            category=category,
            quantity_product_account= len(category.product_accounts),
            lang=language
        )

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
        number_buttons_in_row: int = 1,
        is_accounts_storage: bool = False,
        price_one_account: int = 0,
        cost_price_one_account: int = 0
) -> AccountCategoryFull:
    """
    Создаст новый AccountCategories и закэширует его.


    :param account_service_id: Сервис у данной категории.
    :param language: Код языка ("ru","en"...)
    :param parent_id: ID другой категории для которой новая категория будет дочерней и тем самым будет находиться
    ниже по иерархии. Если не указывать, то будет категорией которая находится сразу после сервиса (главной).
    :param number_buttons_in_row: Количество кнопок для перехода в другую категорию на одну строку от 1 до 8.
    :param is_accounts_storage: Флаг установки категории хранилищем аккаунтов.
    :param price_one_account: Цена одного аккаунта.
    :param cost_price_one_account: Себестоимость аккаунта.
    :return: AccountCategories: только что созданный.
    :exception AccountServiceNotFound: Если account_service_id не найден.
    :exception TheCategoryStorageAccount: Если parent_id не является хранилищем аккаунтов.
    """

    if price_one_account is not None and price_one_account < 0:
        raise IncorrectedAmountSale("Цена аккаунтов должна быть положительным числом")
    if cost_price_one_account is not None and cost_price_one_account < 0:
        raise IncorrectedCostPrice("Себестоимость аккаунтов должна быть положительным числом")
    if number_buttons_in_row is not None and (number_buttons_in_row < 1 or number_buttons_in_row > 8):
        raise IncorrectedNumberButton("Количество кнопок в строке, должно быть в диапазоне от 1 до 8")

    if not await get_account_service(account_service_id, return_not_show=True):
        raise AccountServiceNotFound(f"Сервис для аккаунтов с id = {account_service_id} не найдена")

    if parent_id:
        parent_category = await get_account_categories_by_category_id(parent_id, return_not_show=True)
        if not parent_category:
            raise AccountCategoryNotFound()
        if parent_category.is_accounts_storage:
            raise TheCategoryStorageAccount(
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

        # создание простой фото заглушки с белым фоном
        file_data = get_default_image_bytes()
        key = str(uuid.uuid4())
        new_ui_image = await create_ui_image(key=key, file_data=file_data, show=False)

        # создание категории
        new_account_categories = AccountCategories(
            account_service_id = account_service_id,
            parent_id = parent_id,
            ui_image_key = new_ui_image.key,
            index = new_index,
            number_buttons_in_row = number_buttons_in_row,
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


async def add_account_storage(
    type_service_name: str,
    checksum: str,
    encrypted_key: str,
    phone_number: str,

    status: Literal["for_sale", "bought", "deleted"] = 'for_sale',
    key_version: int = 1,
    encryption_algo: str = 'AES-GCM-256',
    login_encrypted: str = None,
    password_encrypted: str = None,
) -> AccountStorage:
    """
    Путь сформируется только для аккаунтов телеграмма т.к. только их данные хранятся в файле.
     Преобразует номер телефона в необходимый формат для хранения (E164)
    :param type_service_name: Имя сервиса необходимо для формирования пути (должен иметься в TYPE_ACCOUNT_SERVICES)
    :param checksum: Контроль целостности (SHA256 зашифрованного файла)
    :param encrypted_key: Персональный ключ аккаунта, зашифрованный мастер-ключом (DEK)
    :param phone_number: номер телефона
    :param status: статус
    :param key_version: Номер мастер-ключа (для ротации)
    :param encryption_algo: Алгоритм шифрования
    :param login_encrypted: Зашифрованный логин
    :param password_encrypted: Зашифрованный Пароль
    """
    if type_service_name not in TYPE_ACCOUNT_SERVICES:
        raise ValueError(f"type_service_name = {type_service_name} не найден")

    # только для аккаунтов телеграмм формируем путь
    storage_uuid = str(uuid.uuid4()) if type_service_name == 'telegram' else None
    file_path = Path(status) / type_service_name / str(storage_uuid) / 'account.zip.enc' if type_service_name == 'telegram' else None

    if type_service_name != 'telegram' and (login_encrypted is None or password_encrypted is None):
        raise ValueError(f"Необходимо указать login_encrypted и password_encrypted")

    new_account_storage = AccountStorage(
        storage_uuid = storage_uuid,
        file_path = str(file_path), # относительный путь к зашифрованному файлу (относительно accounts/)
        checksum = checksum,
        status = status,
        encrypted_key = encrypted_key,
        key_version = key_version,
        encryption_algo = encryption_algo,
        phone_number = phone_in_e164(phone_number),
        login_encrypted = login_encrypted,
        password_encrypted = password_encrypted
    )

    async with get_db() as session_db:
        session_db.add(new_account_storage)
        await session_db.commit()
        await session_db.refresh(new_account_storage)

    if type_service_name == 'telegram':
        tg_media = TgAccountMedia(
            account_storage_id=new_account_storage.account_storage_id
        )
        async with get_db() as session_db:
            session_db.add(tg_media)
            await session_db.commit()

    return new_account_storage


async def add_product_account(
    account_category_id: int,
    account_storage_id: int,
) -> ProductAccounts:
    """
    Добавится аккаунт в категорию только где is_accounts_storage = True.
    У аккаунта будет присвоен тип сервиса такой же как у категории
    """

    category = await get_account_categories_by_category_id(account_category_id, return_not_show=True)
    if not category:
        raise CategoryNotFound(f"Категория аккаунтов с id = {account_category_id} не найдена")
    elif not category.is_accounts_storage:
        raise TheCategoryNotStorageAccount(
            f"Категория аккаунтов с id = {account_category_id} не является хранилищем аккаунтов. "
            f"для добавления аккаунтов необходимо сделать хранилищем"
        )

    service = await get_account_service(category.account_service_id, return_not_show=True)
    new_product_account = ProductAccounts(
        type_account_service_id = service.type_account_service_id,
        account_category_id = account_category_id,
        account_storage_id = account_storage_id,
    )

    async with get_db() as session_db:
        session_db.add(new_product_account)
        await session_db.commit()
        await session_db.refresh(new_product_account)

    all_account = await get_product_account_by_category_id(account_category_id)
    new_list_accounts = [new_product_account.to_dict()]
    for account in all_account:
        new_list_accounts.append(account.to_dict())

    # заполнение redis
    # конкретно аккаунты
    await filling_product_account_by_account_id(new_product_account.account_id)
    await filling_product_accounts_by_category_id()

    # категории
    await filling_account_categories_by_service_id()
    await filling_account_categories_by_category_id()
    return new_product_account


async def add_translation_in_sold_account(
    sold_account_id: int,
    language: str,
    name: str,
    description: str,
    filling_redis: bool = True
) -> SoldAccountSmall:
    """Добавит перевод и закэширует"""

    async with get_db() as session_db:
        result_db = await session_db.execute(select(SoldAccounts).where(SoldAccounts.sold_account_id == sold_account_id))
        sold_account: SoldAccounts = result_db.scalar_one_or_none()
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
            raise TranslationAlreadyExists(f"Перевод по данному языку '{language}' уже есть")

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
            .options(selectinload(SoldAccounts.translations), selectinload(SoldAccounts.account_storage))
            .where(SoldAccounts.sold_account_id == sold_account_id)
        )
        sold_account = result_db.scalar_one_or_none()

        full_sold_account = SoldAccountSmall.from_orm_with_translation(sold_account, language)

    # заполнение redis
    if filling_redis:
        await filling_sold_accounts_by_owner_id(sold_account.owner_id)
        await filling_sold_account_by_account_id(sold_account_id)

    return full_sold_account


async def add_sold_account(
    owner_id: int,
    type_account_service_id: int,
    account_storage_id: int,
    language: str,
    name: str,
    description: str,
) -> SoldAccountSmall:
    """Сделает запись в БД, и закэширует"""
    if not await get_user(owner_id):
        raise ValueError(f"Пользователь с ID = {owner_id} не найден")

    if not await get_type_account_service(type_account_service_id):
        raise ValueError(f"Тип сервиса с ID = {type_account_service_id} не найден")

    new_sold_account = SoldAccounts(
        owner_id = owner_id,
        account_storage_id = account_storage_id,
        type_account_service_id = type_account_service_id
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
        account_storage_id: int,
        category_name: str,
        description: str
) -> DeletedAccounts:

    if not await get_type_account_service(type_account_service_id):
        raise ValueError(f"Тип сервиса с id = {type_account_service_id} не найден")

    async with get_db() as session_db:
        new_deleted_account = DeletedAccounts(
            type_account_service_id = type_account_service_id,
            account_storage_id = account_storage_id,
            category_name = category_name,
            description = description
        )

        session_db.add(new_deleted_account)
        await session_db.commit()
        await session_db.refresh(new_deleted_account)

    return new_deleted_account