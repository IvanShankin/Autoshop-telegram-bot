import os
import uuid
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from tests.helpers.func_fabrics.category_fabric import create_category_factory
from tests.helpers.func_fabrics.other_fabric import create_new_user_fabric

from src.services.database.categories.models import AccountStorage, TgAccountMedia, Purchases
from src.services.database.categories.models import SoldAccounts, SoldAccountsTranslation, \
    ProductAccounts, \
    SoldAccountFull, SoldAccountSmall, ProductAccountFull
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.core.database import get_db
from src.services.redis.filling import filling_sold_accounts_by_owner_id, \
    filling_sold_account_by_account_id, filling_all_keys_category, filling_product_account_by_account_id
from src.services.secrets import encrypt_text, get_crypto_context, make_account_key


def make_fake_encrypted_archive_for_test(
        account_key: bytes,
        status: str = "for_sale",
        type_account_service: AccountServiceType = AccountServiceType.TELEGRAM
) -> str:
    """
    Создаёт зашифрованный архив аккаунта в структуре проекта:
    accounts/<status>/<type_account_service>/<uuid>/account.enc

    Архив можно расшифровать с помощью переданного account_key.

    Внутри архива (после расшифровки):
    ├── session.session
    └── tdata/
        └── loans.txt
    """

    from src.services.filesystem.media_paths import create_path_account
    # генерируем UUID
    # === 1. Генерация UUID и путей ===
    account_uuid = str(uuid.uuid4())
    encrypted_path = create_path_account(status, type_account_service, account_uuid)
    account_dir = Path(os.path.dirname(encrypted_path))
    os.makedirs(account_dir, exist_ok=True)

    # === 2. Создаём файлы для архива ===
    session_file = account_dir / "session.session"
    tdata_dir = account_dir / "tdata"
    loans_file = tdata_dir / "loans.txt"

    tdata_dir.mkdir(exist_ok=True)

    # session.session
    with open(session_file, "w", encoding="utf-8") as f:
        f.write("hello world")

    # loans.txt
    with open(loans_file, "w", encoding="utf-8") as f:
        f.write("login details")

    # === 3. Создаём zip-архив с нужной структурой ===
    zip_path = account_dir / "archive.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Добавляем session.session в корень архива
        zf.write(session_file, arcname="session.session")

        # Добавляем loans.txt внутрь tdata/
        zf.write(loans_file, arcname="tdata/loans.txt")

    # === 4. Шифруем zip-файл с помощью AES-GCM ===
    aesgcm = AESGCM(account_key)
    nonce = os.urandom(12)

    with open(zip_path, "rb") as f:
        data = f.read()

    ciphertext = aesgcm.encrypt(nonce, data, None)

    # === 5. Сохраняем как account.enc ===
    with open(encrypted_path, "wb") as f:
        f.write(nonce + ciphertext)

    # === 6. Удаляем временные файлы ===
    os.remove(zip_path)
    os.remove(session_file)
    os.remove(loans_file)
    os.rmdir(tdata_dir)

    return encrypted_path



async def create_account_storage_factory(
        is_active: bool = True,
        is_valid: bool = True,
        status: str = 'for_sale',
        phone_number: str = '+7 920 107-42-12'
) -> AccountStorage:
    crypto = get_crypto_context()
    encrypted_key_b64, account_key, encrypted_key_nonce = make_account_key(crypto.kek)
    file_path = make_fake_encrypted_archive_for_test(account_key, status)

    login_encrypted, login_nonce, _ = encrypt_text('login_encrypted', account_key)
    password_encrypted, password_nonce, _ = encrypt_text('password_encrypted', account_key)

    account_storage = AccountStorage(
        file_path = file_path,
        checksum = "checksum",

        encrypted_key = encrypted_key_b64,
        encrypted_key_nonce = encrypted_key_nonce,

        phone_number = phone_number,
        login_encrypted = login_encrypted,
        login_nonce = login_nonce,
        password_encrypted = password_encrypted,
        password_nonce = password_nonce,

        is_active = is_active,
        is_valid = is_valid,
        status = status
    )
    async with get_db() as session_db:
        session_db.add(account_storage)
        await session_db.commit()
        await session_db.refresh(account_storage)
        return account_storage


async def create_product_account_factory(
        filling_redis: bool = True,
        type_account_service: AccountServiceType = AccountServiceType.TELEGRAM,
        category_id: int = None,
        account_storage_id: int = None,
        status: str = 'for_sale',
        phone_number: str = '+7 920 107-42-12',
        price: int = 150
) -> (ProductAccounts, ProductAccountFull):
    async with get_db() as session_db:
        if category_id is None:
            category = await create_category_factory(filling_redis=filling_redis, price=price)
            category_id = category.category_id
        if account_storage_id is None:
            account_storage = await create_account_storage_factory(status=status, phone_number=phone_number)
            account_storage_id = account_storage.account_storage_id
        else:
            account_storage = None

        new_account = ProductAccounts(
            category_id = category_id,
            type_account_service = type_account_service,
            account_storage_id = account_storage_id,
        )
        session_db.add(new_account)
        await session_db.commit()
        result_db = await session_db.execute((
            select(ProductAccounts)
            .options(selectinload(ProductAccounts.account_storage))
            .where(ProductAccounts.account_id == new_account.account_id)
        ))
        new_account = result_db.scalar()

        if filling_redis:
            await filling_product_account_by_account_id(new_account.account_id)

            # связанные таблицы
            await filling_all_keys_category()

        if not account_storage:
            result_db = await session_db.execute(
                select(AccountStorage)
                .where(AccountStorage.account_storage_id == account_storage_id)
            )
            account_storage = result_db.scalar()

    return new_account, ProductAccountFull.from_orm_model(new_account, account_storage)


async def create_sold_account_factory(
        filling_redis: bool = True,
        owner_id: int = None,
        type_account_service: AccountServiceType = AccountServiceType.TELEGRAM,
        account_storage_id: int = None,
        is_active: bool = True,
        is_valid: bool = True,
        language: str = "ru",
        name: str = "name",
        description: str = "description",
        phone_number: str = "+7 920 107-42-12"
) -> (SoldAccountSmall, SoldAccountFull):
    async with get_db() as session_db:
        if owner_id is None:
            user = await create_new_user_fabric()
            owner_id = user.user_id
        if account_storage_id is None:
            account_storage = await create_account_storage_factory(
                is_active, is_valid, 'bought', phone_number=phone_number
            )
            account_storage_id = account_storage.account_storage_id

        new_sold_account = SoldAccounts(
            owner_id = owner_id,
            type_account_service = type_account_service,
            account_storage_id = account_storage_id,
        )

        session_db.add(new_sold_account)
        await session_db.commit()
        await session_db.refresh(new_sold_account)

        new_translate = SoldAccountsTranslation(
            sold_account_id = new_sold_account.sold_account_id,
            lang = language,
            name = name,
            description = description
        )
        session_db.add(new_translate)
        await session_db.commit()

        # Перечитываем объект с подгруженными translations
        result = await session_db.execute(
            select(SoldAccounts)
            .options(selectinload(SoldAccounts.translations), selectinload(SoldAccounts.account_storage))
            .where(SoldAccounts.sold_account_id == new_sold_account.sold_account_id)
        )
        new_sold_account = result.scalar_one()

        full_account = SoldAccountFull.from_orm_with_translation(new_sold_account, language)
        new_sold_account = SoldAccountSmall.from_orm_with_translation(new_sold_account, language)

    if filling_redis:
        await filling_sold_accounts_by_owner_id(full_account.owner_id)
        await filling_sold_account_by_account_id(full_account.sold_account_id)

    return new_sold_account, full_account


async def create_tg_account_media_factory(
    account_storage_id: int = None,
    tdata_tg_id: str = None,
    session_tg_id: str = None
) -> TgAccountMedia:
    if account_storage_id is None:
        account_storage = await create_account_storage_factory()
        account_storage_id = account_storage.account_storage_id

    async with get_db() as session_db:
        new_tg_media = TgAccountMedia(
            account_storage_id=account_storage_id,
            tdata_tg_id=tdata_tg_id,
            session_tg_id=session_tg_id,
        )

        session_db.add(new_tg_media)
        await session_db.commit()
        await session_db.refresh(new_tg_media)

        return new_tg_media


async def create_purchase_fabric(
    user_id: int = None,
    account_storage_id: int = None,
    universal_storage_id: int = None,
    original_price: int = 110,
    purchase_price: int = 100,
    cost_price: int = 50,
    net_profit: int = 50,
) -> Purchases:
    if user_id is None:
        user = await create_new_user_fabric()
        user_id = user.user_id

    if account_storage_id is None:
        acc_storage = await create_account_storage_factory()
        account_storage_id = acc_storage.account_storage_id

    async with get_db() as session_db:
        new_purchase_account = Purchases(
            user_id = user_id,
            account_storage_id = account_storage_id,
            universal_storage_id = universal_storage_id,
            original_price = original_price,
            purchase_price = purchase_price,
            cost_price = cost_price,
            net_profit = net_profit
        )

        session_db.add(new_purchase_account)
        await session_db.commit()
        await session_db.refresh(new_purchase_account)

        return new_purchase_account