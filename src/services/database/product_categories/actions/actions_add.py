import uuid
from pathlib import Path
from typing import Literal

import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config import get_config
from src.exceptions import TranslationAlreadyExists, \
    AccountCategoryNotFound, IncorrectedNumberButton, IncorrectedAmountSale, IncorrectedCostPrice, \
    TheCategoryStorageAccount, CategoryNotFound, TheCategoryNotStorageAccount
from src.services.database.product_categories.models import AccountStorage
from src.services.database.product_categories.models import TgAccountMedia
from src.services.database.product_categories.models.product_account import AccountServiceType
from src.services.database.system.actions.actions import create_ui_image
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db
from src.services.database.product_categories.actions.actions_get import get_account_categories_by_category_id, \
    _get_account_categories_by_service_id, get_product_account_by_category_id
from src.services.database.product_categories.models import Categories, CategoryTranslation, \
    ProductAccounts, SoldAccounts, SoldAccountsTranslation, DeletedAccounts, CategoryFull, SoldAccountSmall
from src.services.database.users.actions import get_user
from src.services.redis.filling_redis import filling_product_account_by_account_id, \
    filling_product_by_category_id, filling_sold_accounts_by_owner_id, filling_sold_account_by_account_id, \
    filling_account_categories_by_service_id, filling_account_categories_by_category_id
from src.utils.pars_number import phone_in_e164
from src.utils.ui_images_data import get_default_image_bytes



async def add_translation_in_category(
        category_id: int,
        language: str,
        name: str,
        description: str = None,
) -> CategoryFull:
    """
    Добавит перевод для Categories и закэширует.
    :param language: Код языка ("ru","en"...)
    :exception AccountCategoryNotFound: Если category_id не найден. Если перевод по данному языку есть
    """
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Categories)
            .where(Categories.category_id == category_id)
        )
        category: Categories = result_db.scalar_one_or_none()

        if not category:
            raise AccountCategoryNotFound(f"Категории с id = {category_id} не найдено")

        result_db = await session_db.execute(
            select(CategoryTranslation)
            .where(
                (CategoryTranslation.category_id == category_id) &
                (CategoryTranslation.lang == language)
            )
        )
        translation: CategoryTranslation = result_db.scalar_one_or_none()
        if translation:
            raise ValueError(f"Перевод по данному языку '{language}' уже есть")

        new_translation = CategoryTranslation(
            category_id = category_id,
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
            select(Categories)
            .options(
                selectinload(Categories.translations),
                selectinload(Categories.products)
            )
            .where(Categories.category_id == category_id)
        )
        category = result_db.scalar_one()

        full_category = CategoryFull.from_orm_with_translation(
            category=category,
            quantity_product= len(category.products),
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
            f"account_categories_by_category_id:{category_id}:{language}",
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
        is_product_storage: bool = False,
        price_one_account: int = 0,
        cost_price_one_account: int = 0
) -> CategoryFull:
    """
    Создаст новый Categories и закэширует его.


    :param account_service_id: Сервис у данной категории.
    :param language: Код языка ("ru","en"...)
    :param parent_id: ID другой категории для которой новая категория будет дочерней и тем самым будет находиться
    ниже по иерархии. Если не указывать, то будет категорией которая находится сразу после сервиса (главной).
    :param number_buttons_in_row: Количество кнопок для перехода в другую категорию на одну строку от 1 до 8.
    :param is_product_storage: Флаг установки категории хранилищем аккаунтов.
    :param price_one_account: Цена одного аккаунта.
    :param cost_price_one_account: Себестоимость аккаунта.
    :return: Categories: только что созданный.
    :exception AccountServiceNotFound: Если account_service_id не найден.
    :exception TheCategoryStorageAccount: Если parent_id не является хранилищем аккаунтов.
    """

    if price_one_account is not None and price_one_account < 0:
        raise IncorrectedAmountSale("Цена аккаунтов должна быть положительным числом")
    if cost_price_one_account is not None and cost_price_one_account < 0:
        raise IncorrectedCostPrice("Себестоимость аккаунтов должна быть положительным числом")
    if number_buttons_in_row is not None and (number_buttons_in_row < 1 or number_buttons_in_row > 8):
        raise IncorrectedNumberButton("Количество кнопок в строке, должно быть в диапазоне от 1 до 8")

    if parent_id:
        parent_category = await get_account_categories_by_category_id(parent_id, return_not_show=True)
        if not parent_category:
            raise AccountCategoryNotFound()
        if parent_category.is_product_storage:
            raise TheCategoryStorageAccount(
                f"Родительский аккаунт (parent_id = {parent_id}) является хранилищем аккаунтов. "
                f"К данной категории нельзя прикрепить другую категорию"
            )

    async with get_db() as session_db:
        if parent_id:
            is_main = False
            result_db = await session_db.execute(
                select(Categories)
                .where(Categories.parent_id == parent_id)
            )

        else:
            is_main = True
            result_db = await session_db.execute(
                select(Categories)
                .where(Categories.is_main == True)
            )

        categories = result_db.scalars().all()
        new_index = max((category.index for category in categories), default=-1) + 1

        # создание простой фото заглушки с белым фоном
        file_data = get_default_image_bytes()
        key = str(uuid.uuid4())
        new_ui_image = await create_ui_image(key=key, file_data=file_data, show=False)

        # создание категории
        new_account_categories = Categories(
            account_service_id = account_service_id,
            parent_id = parent_id,
            ui_image_key = new_ui_image.key,
            index = new_index,
            number_buttons_in_row = number_buttons_in_row,
            is_main = is_main,
            is_product_storage = is_product_storage,

            # только для тех категорий которые хранят аккаунты (is_product_storage == True)
            price_one_account = price_one_account,
            cost_price_one_account = cost_price_one_account
        )
        session_db.add(new_account_categories)
        await session_db.commit()
        await session_db.refresh(new_account_categories)

    return await add_translation_in_category(
        category_id = new_account_categories.category_id,
        language = language,
        name = name,
        description = description
    )


async def add_account_storage(
    type_service_name: str,
    checksum: str,
    encrypted_key: str,
    encrypted_key_nonce: str,
    phone_number: str,

    status: Literal["for_sale", "bought", "deleted"] = 'for_sale',
    key_version: int = 1,
    encryption_algo: str = 'AES-GCM-256',
    login_encrypted: str = None,
    login_nonce: str = None,
    password_encrypted: str = None,
    password_nonce: str = None,
) -> AccountStorage:
    """
    Путь сформируется только для аккаунтов телеграмма т.к. только их данные хранятся в файле.
     Преобразует номер телефона в необходимый формат для хранения (E164)
    :param type_service_name: Имя сервиса необходимо для формирования пути (должен иметься в get_config().app.type_account_services)
    :param checksum: Контроль целостности (SHA256 зашифрованного файла)
    :param encrypted_key: Персональный ключ аккаунта, зашифрованный мастер-ключом (DEK)
    :param encrypted_key_nonce: nonce, использованный при wrap (Nonce (IV) для AES-GCM (base64))
    :param phone_number: номер телефона
    :param status: статус
    :param key_version: Номер мастер-ключа (для ротации)
    :param encryption_algo: Алгоритм шифрования
    :param login_encrypted: Зашифрованный логин
    :param login_nonce: используемый nonce при шифровании
    :param password_encrypted: Зашифрованный Пароль
    :param password_nonce:  используемый nonce при шифровании
    """
    if type_service_name not in get_config().app.type_account_services:
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
        encrypted_key_nonce=encrypted_key_nonce,
        key_version = key_version,
        encryption_algo = encryption_algo,
        phone_number = phone_in_e164(phone_number),
        login_encrypted = login_encrypted,
        login_nonce = login_nonce,
        password_encrypted = password_encrypted,
        password_nonce = password_nonce
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
    type_account_service: str,
    category_id: int,
    account_storage_id: int,
) -> ProductAccounts:
    """
    Добавится аккаунт в категорию только где is_product_storage = True.
    У аккаунта будет присвоен тип сервиса такой же как у категории
    """

    category = await get_account_categories_by_category_id(category_id, return_not_show=True)
    if not category:
        raise CategoryNotFound(f"Категория аккаунтов с id = {category_id} не найдена")
    elif not category.is_product_storage:
        raise TheCategoryNotStorageAccount(
            f"Категория аккаунтов с id = {category_id} не является хранилищем аккаунтов. "
            f"для добавления аккаунтов необходимо сделать хранилищем"
        )

    if not any(type_account_service == member.value for member in AccountServiceType):
        raise ValueError(f"Тип сервиса = {type_account_service} не найден")

    new_product_account = ProductAccounts(
        type_account_service = type_account_service,
        category_id = category_id,
        account_storage_id = account_storage_id,
    )

    async with get_db() as session_db:
        session_db.add(new_product_account)
        await session_db.commit()
        await session_db.refresh(new_product_account)

    all_account = await get_product_account_by_category_id(category_id)
    new_list_accounts = [new_product_account.to_dict()]
    for account in all_account:
        new_list_accounts.append(account.to_dict())

    # заполнение redis
    # конкретно аккаунты
    await filling_product_account_by_account_id(new_product_account.account_id)
    await filling_product_by_category_id()

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
    type_account_service: str,
    account_storage_id: int,
    language: str,
    name: str,
    description: str,
) -> SoldAccountSmall:
    """Сделает запись в БД, и закэширует"""
    if not await get_user(owner_id):
        raise ValueError(f"Пользователь с ID = {owner_id} не найден")

    if not any(type_account_service == member.value for member in AccountServiceType):
        raise ValueError(f"Тип сервиса = {type_account_service} не найден")

    new_sold_account = SoldAccounts(
        owner_id = owner_id,
        account_storage_id = account_storage_id,
        type_account_service = type_account_service
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
        type_account_service: str,
        account_storage_id: int,
        category_name: str,
        description: str
) -> DeletedAccounts:

    if not any(type_account_service == member.value for member in AccountServiceType):
        raise ValueError(f"Тип сервиса = {type_account_service} не найден")

    async with get_db() as session_db:
        new_deleted_account = DeletedAccounts(
            type_account_service = type_account_service,
            account_storage_id = account_storage_id,
            category_name = category_name,
            description = description
        )

        session_db.add(new_deleted_account)
        await session_db.commit()
        await session_db.refresh(new_deleted_account)

    return new_deleted_account