import os, base64
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import orjson
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config import SECRET_KEY
from src.services.database.selling_accounts.models.models import AccountStorage, TgAccountMedia
from src.services.redis.core_redis import get_redis
from src.services.redis.filling_redis import filling_sold_accounts_by_owner_id, \
    filling_sold_account_by_account_id, filling_account_categories_by_service_id, \
    filling_account_categories_by_category_id, filling_all_account_services, filling_account_services, \
    filling_product_account_by_account_id, filling_product_accounts_by_category_id, filling_all_types_payments, \
    filling_types_payments_by_id
from src.services.database.admins.models import Admins
from src.services.database.discounts.models import Vouchers
from src.services.database.referrals.utils import create_unique_referral_code
from src.services.database.selling_accounts.models import SoldAccounts, TypeAccountServices, SoldAccountsTranslation, \
    AccountServices, AccountCategories, AccountCategoryTranslation, ProductAccounts, \
    SoldAccountFull, AccountCategoryFull, SoldAccountSmall, ProductAccountFull
from src.services.database.system.models import UiImages
from src.services.database.users.models import Users, Replenishments, NotificationSettings, WalletTransaction
from src.services.database.system.models import TypePayments
from src.services.database.core.database import get_db
from src.services.database.referrals.models import Referrals, IncomeFromReferrals
from src.utils.secret_data import encrypt_data


def make_fake_account_key_for_test() -> tuple[str, bytes]:
    """Создаёт случайный account_key и его base64-зашифрованную версию через master_key."""
    master_key = base64.b64decode(SECRET_KEY)
    account_key = os.urandom(32)
    aesgcm = AESGCM(master_key)
    nonce = os.urandom(12)
    wrapped = nonce + aesgcm.encrypt(nonce, account_key, None)
    return base64.b64encode(wrapped).decode(), account_key


def make_fake_encrypted_archive_for_test(account_key: bytes, status: str = "for_sale", type_account_service: str = "telegram") -> str:
    """
    Создаёт зашифрованный архив аккаунта в структуре проекта:
    accounts/<status>/<type_account_service>/<uuid>/account.enc

    Архив можно расшифровать с помощью переданного account_key.

    Внутри архива (после расшифровки):
    ├── session.session
    └── tdata/
        └── loans.txt
    """

    from src.services.filesystem.account_actions import create_path_account
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



async def create_new_user_fabric(user_name: str = "test_username", union_ref_code: str = None, balance: int = 0) -> Users:
    """ Создаст нового пользователя в БД"""
    if union_ref_code is None:
        union_ref_code = await create_unique_referral_code()


    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users.user_id))
        max_id = result_db.scalars().all()

        new_id = max(max_id, default=-1) + 1

        new_user = Users(
            user_id=new_id,
            username=user_name,
            balance=balance,
            unique_referral_code=union_ref_code,
        )

        session_db.add(new_user)
        await session_db.commit()
        await session_db.refresh(new_user)

        new_notifications = NotificationSettings(
           user_id=new_user.user_id
        )
        session_db.add(new_notifications)
        await session_db.commit()

    return new_user



async def create_admin_fabric(filling_redis: bool = True, user_id: int = None) -> Admins:
    if user_id is None:
        user = await create_new_user_fabric()
        user_id = user.user_id

    async with get_db() as session_db:
        new_admin = Admins(user_id = user_id)
        session_db.add(new_admin)
        await session_db.commit()
        await session_db.refresh(new_admin)

    if filling_redis:
        async with get_redis() as session_redis:
            await session_redis.set(f"admin:{new_admin.user_id}", '_')

    return new_admin




async def create_referral_fabric(owner_id: int = None) -> (Referrals, Users, Users):
    """
       Создаёт тестовый реферала (у нового пользователя появляется владелец)
       :return Реферал(Referrals), Владельца(Users) и Реферала(Users)
    """
    async with get_db() as session_db:
        user = await create_new_user_fabric() # новый реферал

        if owner_id is None: # создаём владельца
            owner = await create_new_user_fabric(user_name='owner_user')
            owner_id = owner.user_id
        else:
            result_db = await session_db.execute(select(Users).where(Users.user_id == owner_id))
            owner = result_db.scalar()

        # связываем реферала и владельца
        referral = Referrals(
            referral_id=user.user_id,
            owner_user_id=owner_id,
            level=1,
        )
        session_db.add(referral)
        await session_db.commit()
        await session_db.refresh(referral)

    return referral, owner, user



async def create_income_from_referral_fabric(
        referral_user_id: int = None,
        owner_id: int = None,
        replenishment_id: int = None,
        amount: int = 100,
        percentage_of_replenishment: int = 5,
) -> (IncomeFromReferrals, Users):
    """
        Создаёт доход от реферала, если не указать реферала, то создаст нового, если не указать владельца, то создаст нового.
        :return Доход(IncomeFromReferrals), Реферал(Users), Владелец(Users)
    """
    async with get_db() as session_db:
        if owner_id is None: # создаём владельца
            owner = await create_new_user_fabric(user_name='owner_user')
            owner_id = owner.user_id
        else:
            result_db = await session_db.execute(select(Users).where(Users.user_id == owner_id))
            owner = result_db.scalar()
        if referral_user_id is None:
            referral = await create_new_user_fabric(user_name='referral_user')
            referral_user_id = referral.user_id
        else:
            result_db = await session_db.execute(select(Users).where(Users.user_id == referral_user_id))
            referral = result_db.scalar()
        if replenishment_id is None:
            replenishment = await create_replenishment_fabric()
            replenishment_id = replenishment.replenishment_id

        new_income = IncomeFromReferrals(
            replenishment_id=replenishment_id,
            owner_user_id = owner_id,
            referral_id = referral_user_id,
            amount = amount,
            percentage_of_replenishment = percentage_of_replenishment,
        )

        session_db.add(new_income)
        await session_db.commit()
        await session_db.refresh(new_income)

    return new_income, referral, owner



async def create_replenishment_fabric(amount: int = 110) -> Replenishments:
    """Создаёт пополнение для пользователя"""
    async with get_db() as session_db:
        user = await create_new_user_fabric()
        # создаём тип платежа (если ещё нет)
        result = await session_db.execute(select(TypePayments))
        type_payment = result.scalars().first()
        if not type_payment:
            type_payment = TypePayments(
                name_for_user="TestPay",
                name_for_admin="TestPayAdmin",
                index=1,
                commission=0.0,
            )
            session_db.add(type_payment)
            await session_db.commit()
            await session_db.refresh(type_payment)

        repl = Replenishments(
            user_id=user.user_id,
            type_payment_id=type_payment.type_payment_id,
            origin_amount=100,
            amount=amount, # сумма пополнения
            status="completed",
        )
        session_db.add(repl)
        await session_db.commit()
        await session_db.refresh(repl)

    return repl


async def create_type_payment_factory(
        filling_redis: bool = True,
        name_for_user: str = None,
        name_for_admin: str = None,
        is_active: bool = None,
        commission: float = None,
        index: int = None,
        extra_data: dict = None,
) -> TypePayments:
    """Создаст новый тип оплаты в БД"""
    async with get_db() as session_db:
        if index is None:
            result = await session_db.execute(select(TypePayments))
            all_types = result.scalars().all()
            index = max((service.index for service in all_types),default=-1) + 1  # вычисляем максимальный индекс

        new_type_payment = TypePayments(
            name_for_user= name_for_user if name_for_user else "Test Payment Method",
            name_for_admin= name_for_admin if name_for_admin else "Test Payment Method (Admin)",
            is_active= is_active if is_active else True,
            commission= commission if commission else 5,
            index= index,
            extra_data= extra_data if extra_data else {"api_key": "test_key", "wallet_id": "test_wallet"}
        )

        session_db.add(new_type_payment)
        await session_db.commit()
        await session_db.refresh(new_type_payment)

        if filling_redis:
            await filling_all_types_payments()

            result = await session_db.execute(select(TypePayments))
            all_types = result.scalars().all()
            for type_payment in all_types:
                await filling_types_payments_by_id(type_payment.type_payment_id)

    return new_type_payment


async def create_voucher_factory(
        filling_redis: bool = True,
        creator_id: int = None,
        expire_at: datetime = datetime.now(timezone.utc) + timedelta(days=1),
        is_valid: bool = True
) -> Vouchers:
    """Создаст новый ваучер в БД и в redis."""
    if creator_id is None:
        user = await create_new_user_fabric()
        creator_id = user.user_id

    voucher = Vouchers(
        creator_id=creator_id,
        activation_code="TESTCODE",
        amount=100,
        activated_counter=0,
        number_of_activations=5,
        expire_at=expire_at,
        is_valid=is_valid,
    )

    async with get_db() as session_db:
        session_db.add(voucher)
        await session_db.commit()
        await session_db.refresh(voucher)

    if filling_redis:
        async with get_redis() as session_redis:
            promo_dict = voucher.to_dict()
            await session_redis.set(f'voucher:{voucher.activation_code}', orjson.dumps(promo_dict))

    return voucher


async def create_type_account_service_factory(filling_redis: bool = True, name: str = "telegram") -> TypeAccountServices:
    async with get_db() as session_db:
        new_type = TypeAccountServices(name=name)
        session_db.add(new_type)
        await session_db.commit()
        await session_db.refresh(new_type)

    if filling_redis:
        await filling_all_account_services()
        await filling_account_services()

    return new_type


async def create_account_service_factory(
        filling_redis: bool = True,
        name: str = "telegram",
        index: int = None,
        type_account_service_id: int = None,
        show: bool = True,
) -> AccountServices:
    async with get_db() as session_db:
        if index is None:
            result_db = await session_db.execute(select(AccountServices).order_by(AccountServices.index.asc()))
            all_services: list[AccountServices] = result_db.scalars().all()  # тут уже отсортированный по index
            index = max((service.index for service in all_services), default=-1) + 1
        if type_account_service_id is None:
            service = await create_type_account_service_factory(filling_redis=filling_redis)
            type_account_service_id = service.type_account_service_id

        new_service = AccountServices(
            name=name,
            index=index,
            show=show,
            type_account_service_id=type_account_service_id,
        )
        session_db.add(new_service)
        await session_db.commit()
        await session_db.refresh(new_service)

    if filling_redis:
        await filling_all_account_services()
        await filling_account_services()

    return new_service



async def create_translate_account_category_factory(
        category_id: int,
        filling_redis: bool = True,
        language: str = "ru",
        name: str = "name",
        description: str = "description"
) -> AccountCategoryFull:
    async with get_db() as session_db:
        new_translate = AccountCategoryTranslation(
            account_category_id=category_id,
            lang=language,
            name=name,
            description=description
        )
        session_db.add(new_translate)
        await session_db.commit()

        result = await session_db.execute(
            select(AccountCategories)
            .options(selectinload(AccountCategories.translations), selectinload(AccountCategories.product_accounts))
            .where(AccountCategories.account_category_id == category_id)
        )
        category = result.scalar_one()

        full_category = AccountCategoryFull.from_orm_with_translation(
            category = category,
            quantity_product_account = len(category.product_accounts),
            lang = language
        )

    if filling_redis:
        await filling_account_categories_by_service_id()
        await filling_account_categories_by_category_id()

    return full_category


async def create_account_category_factory(
        filling_redis: bool = True,
        account_service_id: int = None,
        parent_id: int = None,
        ui_image_key: str = None,
        index: int = None,
        show: bool = True,
        is_main: bool = True,
        is_accounts_storage: bool = False,
        price_one_account: int = 150,
        cost_price_one_account: int = 100,
        language: str = "ru",
        name: str = "name",
        description: str = "description"
) -> AccountCategoryFull:
    async with get_db() as session_db:
        if account_service_id is None:
            service = await create_account_service_factory(filling_redis=filling_redis)
            account_service_id = service.account_service_id
        if parent_id is not None:
            is_main = False
        if ui_image_key is None:
            ui_image, path = await create_ui_image_factory(key=str(uuid.uuid4()))
            ui_image_key = ui_image.key
        if index is None:
            result_db = await session_db.execute(
                select(AccountCategories)
                .where(AccountCategories.parent_id == parent_id)
                .order_by(AccountCategories.index.asc())
            )
            all_services: list[AccountCategories] = result_db.scalars().all()  # тут уже отсортированный по index
            index = max((service.index for service in all_services), default=-1) + 1

        new_category = AccountCategories(
            account_service_id=account_service_id,
            parent_id = parent_id,
            ui_image_key = ui_image_key,
            index = index,
            show = show,
            is_main = is_main,
            is_accounts_storage = is_accounts_storage,
            price_one_account = price_one_account,
            cost_price_one_account = cost_price_one_account
        )
        session_db.add(new_category)
        await session_db.commit()
        await session_db.refresh(new_category)

        new_translate = AccountCategoryTranslation(
            account_category_id=new_category.account_category_id,
            lang=language,
            name=name,
            description=description
        )
        session_db.add(new_translate)
        await session_db.commit()

        # Перечитываем объект с подгруженными translations
        result = await session_db.execute(
            select(AccountCategories)
            .options(selectinload(AccountCategories.translations), selectinload(AccountCategories.product_accounts))
            .where(AccountCategories.account_category_id == new_category.account_category_id)
        )
        new_category = result.scalar_one()

        full_category = AccountCategoryFull.from_orm_with_translation(
            category = new_category,
            quantity_product_account = len(new_category.product_accounts),
            lang = language,
        )
        if filling_redis:
            await filling_account_categories_by_service_id()
            await filling_account_categories_by_category_id()

    return full_category



async def create_account_storage_factory(
        is_active: bool = True,
        is_valid: bool = True,
        status: str = 'for_sale',
        phone_number: str = '+7 920 107-42-12'
) -> AccountStorage:
    encrypted_key_b64, account_key = make_fake_account_key_for_test()
    file_path = make_fake_encrypted_archive_for_test(account_key, status)

    account_storage = AccountStorage(
        file_path = file_path,
        checksum = "checksum",

        encrypted_key = encrypted_key_b64,
        encrypted_key_nonce = "gnjfdsnjds",

        phone_number = phone_number,
        login_encrypted = encrypt_data('login_encrypted'),
        password_encrypted = encrypt_data('password_encrypted'),

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
        type_account_service_id: int = None,
        account_category_id: int = None,
        account_storage_id: int = None,
        status: str = 'for_sale'
) -> (ProductAccounts, ProductAccountFull):
    async with get_db() as session_db:
        if type_account_service_id is None:
            service_type = await create_type_account_service_factory(filling_redis=filling_redis)
            type_account_service_id = service_type.type_account_service_id
        if account_category_id is None:
            category = await create_account_category_factory(filling_redis=filling_redis)
            account_category_id = category.account_category_id
        if account_storage_id is None:
            account_storage = await create_account_storage_factory(status=status)
            account_storage_id = account_storage.account_storage_id
        else:
            account_storage = None

        new_account = ProductAccounts(
            type_account_service_id = type_account_service_id,
            account_category_id = account_category_id,
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
            await filling_product_accounts_by_category_id()
            await filling_product_account_by_account_id(new_account.account_id)

            # связанные таблицы
            await filling_account_categories_by_category_id()
            await filling_account_categories_by_service_id()

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
        type_account_service_id: int = None,
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
        if type_account_service_id is None:
            service = await create_type_account_service_factory(filling_redis=filling_redis)
            type_account_service_id = service.type_account_service_id
        if account_storage_id is None:
            account_storage = await create_account_storage_factory(
                is_active, is_valid, 'bought', phone_number=phone_number
            )
            account_storage_id = account_storage.account_storage_id

        new_sold_account = SoldAccounts(
            owner_id = owner_id,
            type_account_service_id = type_account_service_id,
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

        full_account = await SoldAccountFull.from_orm_with_translation(new_sold_account, language)
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




async def create_ui_image_factory(key: str = "main_menu", show: bool = True, file_id: str = None):
    """
       сохраняет запись UiImages в БД и возвращает (ui_image, abs_path).
    """
    from src.utils.ui_images_data import UI_SECTIONS
    # Подготовим директорию и файл
    UI_SECTIONS.mkdir(parents=True, exist_ok=True)

    file_abs = UI_SECTIONS / f"{key}.png"
    file_abs.write_bytes(b"fake-image-bytes")       # создаём тестовый файл

    async with get_db() as session:
        ui_image = UiImages(
            key=key,
            file_path=str(file_abs),
            file_id=file_id,
            show=show,
            updated_at=datetime.now(timezone.utc)
        )
        session.add(ui_image)
        await session.commit()
        await session.refresh(ui_image)

    # Вернём модель и абсолютный путь к файлу (для assert'ов)
    return ui_image, file_abs



async def create_wallet_transaction_fabric(user_id: int, type: str = 'replenish', amount: int = 100) -> WalletTransaction:
    if user_id is None:
        user = await create_new_user_fabric()
        user_id = user.user_id

    async with get_db() as session:
        transaction = WalletTransaction(
            user_id = user_id,
            type = type,
            amount = amount,
            balance_before = 0,
            balance_after = 100
        )

        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)
        return transaction
