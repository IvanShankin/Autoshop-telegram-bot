import uuid
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.exceptions import TranslationAlreadyExists, \
    CategoryNotFound, \
    TheCategoryNotStorageAccount
from src.exceptions.business import TheAccountServiceDoesNotMatch
from src.services.database.categories.actions.actions_get import get_category_by_category_id
from src.services.database.categories.models import AccountStorage
from src.services.database.categories.models import ProductAccounts, SoldAccounts, SoldAccountsTranslation, \
    DeletedAccounts, SoldAccountSmall
from src.services.database.categories.models import TgAccountMedia
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.core.database import get_db
from src.services.database.users.actions import get_user
from src.services.redis.filling import filling_product_account_by_account_id, \
    filling_sold_accounts_by_owner_id, filling_sold_account_by_account_id, \
    filling_main_categories, filling_categories_by_parent, filling_category_by_category, \
    filling_product_accounts_by_category_id
from src.utils.pars_number import phone_in_e164


async def add_account_storage(
    type_service_name: AccountServiceType,
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
    tg_id: int = None,
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
    :param password_nonce: используемый nonce при шифровании
    :param tg_id: ID аккаунта в телеграмме. Только для ТГ аккаунтов
    """
    if not type_service_name in AccountServiceType:
        raise ValueError(f"type_service_name = {type_service_name} не найден")

    # только для аккаунтов телеграмм формируем путь
    storage_uuid = str(uuid.uuid4()) if type_service_name == type_service_name.TELEGRAM else None
    file_path = Path(status) / type_service_name.value / str(storage_uuid) / 'account.zip.enc' if type_service_name == AccountServiceType.TELEGRAM else None

    if type_service_name != AccountServiceType.TELEGRAM and (login_encrypted is None or password_encrypted is None):
        raise ValueError(f"Необходимо указать login_encrypted и password_encrypted")

    new_account_storage = AccountStorage(
        storage_uuid = storage_uuid,
        file_path = str(file_path), # относительный путь к зашифрованному файлу (относительно media/accounts/)
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
        password_nonce = password_nonce,
        tg_id = tg_id
    )

    async with get_db() as session_db:
        session_db.add(new_account_storage)
        await session_db.commit()
        await session_db.refresh(new_account_storage)

    if type_service_name == type_service_name.TELEGRAM:
        tg_media = TgAccountMedia(
            account_storage_id=new_account_storage.account_storage_id
        )
        async with get_db() as session_db:
            session_db.add(tg_media)
            await session_db.commit()

    return new_account_storage


async def add_product_account(
    type_account_service: AccountServiceType,
    category_id: int,
    account_storage_id: int,
) -> ProductAccounts:
    """
    Добавится аккаунт в категорию только где is_product_storage = True.
    У аккаунта будет присвоен тип сервиса такой же как у категории
    """

    category = await get_category_by_category_id(category_id, return_not_show=True)
    if not category:
        raise CategoryNotFound(f"Категория аккаунтов с id = {category_id} не найдена")
    elif not category.is_product_storage:
        raise TheCategoryNotStorageAccount(
            f"Категория аккаунтов с id = {category_id} не является хранилищем аккаунтов. "
            f"для добавления аккаунтов необходимо сделать хранилищем"
        )
    elif category.type_account_service != type_account_service:
        raise TheAccountServiceDoesNotMatch(
            f"у категории сервис: {category.type_account_service}, но вы пытаетесь добавить: {type_account_service.value}"
        )

    if not any(type_account_service == member for member in AccountServiceType):
        raise ValueError(f"Тип сервиса = {type_account_service.value} не найден")

    new_product_account = ProductAccounts(
        type_account_service = type_account_service,
        category_id = category_id,
        account_storage_id = account_storage_id,
    )

    async with get_db() as session_db:
        session_db.add(new_product_account)
        await session_db.commit()
        await session_db.refresh(new_product_account)


    # заполнение redis
    # конкретно аккаунты
    await filling_product_account_by_account_id(new_product_account.account_id)
    await filling_product_accounts_by_category_id()

    # категории
    await filling_main_categories(category_id)
    await filling_categories_by_parent(category_id)
    await filling_category_by_category([category.category_id])
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
    type_account_service: AccountServiceType,
    account_storage_id: int,
    language: str,
    name: str,
    description: str,
) -> SoldAccountSmall:
    """Сделает запись в БД, и закэширует"""
    if not await get_user(owner_id):
        raise ValueError(f"Пользователь с ID = {owner_id} не найден")

    if not any(type_account_service == member for member in AccountServiceType):
        raise ValueError(f"Тип сервиса = {type_account_service.value} не найден")

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
        type_account_service: AccountServiceType,
        account_storage_id: int,
        category_name: str,
        description: str
) -> DeletedAccounts:

    if not any(type_account_service == member for member in AccountServiceType):
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