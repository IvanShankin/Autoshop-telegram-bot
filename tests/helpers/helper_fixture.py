from datetime import datetime, timezone, timedelta

import orjson
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.filling_redis import filling_sold_accounts_by_owner_id, \
    filling_sold_accounts_by_accounts_id, filling_account_categories_by_service_id, \
    filling_account_categories_by_category_id, filling_all_account_services, filling_account_services, \
    filling_product_accounts_by_account_id, filling_product_accounts_by_category_id, filling_all_types_payments, \
    filling_types_payments_by_id
from src.services.admins.models import Admins
from src.services.discounts.models import PromoCodes, Vouchers
from src.services.referrals.utils import create_unique_referral_code
from src.services.selling_accounts.models import SoldAccounts, TypeAccountServices, SoldAccountsTranslation, \
    AccountServices, AccountCategories, AccountCategoryTranslation, ProductAccounts
from src.services.selling_accounts.models.models_with_tranlslate import SoldAccountsFull, AccountCategoryFull
from src.services.system.models.models import UiImages
from src.services.users.models import Users, Replenishments, NotificationSettings
from src.services.system.models import TypePayments, Settings
from src.services.database.database import get_db
from src.services.referrals.models import Referrals


@pytest_asyncio.fixture
async def create_new_user():
    """ Создаст нового пользователя в БД"""
    async def _fabric(user_name: str = "test_username", union_ref_code: str = None) -> Users:
        if union_ref_code is None:
            union_ref_code = await create_unique_referral_code()


        async with get_db() as session_db:
            result_db = await session_db.execute(select(Users.user_id))
            max_id = result_db.scalars().all()

            new_id = max(max_id, default=-1) + 1

            new_user = Users(
                user_id=new_id,
                username=user_name,
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

    return _fabric

@pytest_asyncio.fixture
async def create_admin_fix(create_new_user):
    async def _fabric(filling_redis: bool = True, user_id: int = None) -> Admins:
        if user_id is None:
            user = await create_new_user()
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

    return _fabric

@pytest_asyncio.fixture
async def create_referral(create_new_user):
    """
    Создаёт тестовый реферала (у нового пользователя появляется владелец)
    :return Владельца и Реферала
    """
    async def _fabric(owner_id: int = None) -> (Referrals, Users, Users):
        async with get_db() as session_db:
            user = await create_new_user() # новый реферал

            if owner_id is None: # создаём владельца
                owner = await create_new_user(user_name='owner_user')
                owner_id = owner.user_id
            else:
                result_db = await session_db.execute(select(Users).where(Users.user_id == owner_id))
                owner = result_db.scalar()

            # связываем реферала и владельца
            referral = Referrals(
                referral_id=user.user_id,
                owner_user_id=owner_id,
                level=0,
            )
            session_db.add(referral)
            await session_db.commit()
            await session_db.refresh(referral)

        return owner, user

    return _fabric


@pytest_asyncio.fixture
async def create_replenishment(create_new_user)-> Replenishments:
    """Создаёт пополнение для пользователя"""
    async with get_db() as session_db:
        user = await create_new_user()
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
            amount=110, # сумма пополнения
            status="completed",
        )
        session_db.add(repl)
        await session_db.commit()
        await session_db.refresh(repl)

    return repl


@pytest_asyncio.fixture
async def create_type_payment():
    """Создаст новый тип оплаты в БД"""
    async def _factory(
            filling_redis: bool = True,
            name_for_user: str = None,
            name_for_admin: str = None,
            is_active: bool = None,
            commission: float = None,
            index: int = None,
            extra_data: dict = None,
    ) -> TypePayments:
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

    return _factory


@pytest_asyncio.fixture(autouse=True)
async def create_settings() -> Settings:
    settings = Settings(
        support_username='support_username',
        hash_token_logger_bot='hash_token_logger_bot',
        channel_for_logging_id=123456789,
        channel_for_subscription_id=987654321,
        FAQ='FAQ'
    )
    async with get_db() as session_db:
        session_db.add(settings)
        await session_db.commit()
        await session_db.refresh(settings)

    return settings


@pytest_asyncio.fixture
async def create_promo_code() -> PromoCodes:
    """Создаст новый промокод в БД и в redis."""
    promo = PromoCodes(
        activation_code="TESTCODE",
        min_order_amount=100,
        amount=100,
        discount_percentage=None,
        number_of_activations=5,
        expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        is_valid=True,
    )

    async with get_db() as session_db:
        session_db.add(promo)
        await session_db.commit()
        await session_db.refresh(promo)

    async with get_redis() as session_redis:
        promo_dict = promo.to_dict()
        await session_redis.set(f'promo_code:{promo.activation_code}', orjson.dumps(promo_dict))

    return promo

@pytest_asyncio.fixture
async def create_voucher(create_new_user) -> Vouchers:
    """Создаст новый ваучер в БД и в redis."""
    user = await create_new_user()
    voucher = Vouchers(
        creator_id=user.user_id,
        activation_code="TESTCODE",
        amount=100,
        activated_counter=0,
        number_of_activations=5,
        expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        is_valid=True,
    )

    async with get_db() as session_db:
        session_db.add(voucher)
        await session_db.commit()
        await session_db.refresh(voucher)

    async with get_redis() as session_redis:
        promo_dict = voucher.to_dict()
        await session_redis.set(f'voucher:{voucher.activation_code}', orjson.dumps(promo_dict))

    return voucher

@pytest_asyncio.fixture
async def create_type_account_service():
    async def _factory(filling_redis: bool = True, name: str = "service_name") -> TypeAccountServices:
        async with get_db() as session_db:
            new_type = TypeAccountServices(name=name)
            session_db.add(new_type)
            await session_db.commit()
            await session_db.refresh(new_type)

        if filling_redis:
            await filling_all_account_services()
            await filling_account_services()

        return new_type

    return _factory

@pytest_asyncio.fixture
async def create_account_service(create_type_account_service):
    async def _factory(
            filling_redis: bool = True,
            name: str = "service_name",
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
                service = await create_type_account_service(filling_redis=filling_redis)
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

    return _factory


@pytest_asyncio.fixture
async def create_translate_account_category():
    async def _factory(
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
                .options(selectinload(AccountCategories.translations))
                .where(AccountCategories.account_category_id == category_id)
            )
            category = result.scalar_one()

            full_category = AccountCategoryFull.from_orm_with_translation(category, language)

        if filling_redis:
            await filling_account_categories_by_service_id()
            await filling_account_categories_by_category_id()

        return full_category

    return _factory

@pytest_asyncio.fixture
async def create_account_category(create_account_service):
    async def _factory(
            filling_redis: bool = True,
            account_service_id: int = None,
            parent_id: int = None,
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
                service = await create_account_service(filling_redis=filling_redis)
                account_service_id = service.account_service_id
            if parent_id is not None:
                is_main = False
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
                .options(selectinload(AccountCategories.translations))
                .where(AccountCategories.account_category_id == new_category.account_category_id)
            )
            new_category = result.scalar_one()

            full_category = AccountCategoryFull.from_orm_with_translation(new_category, language)
            if filling_redis:
                await filling_account_categories_by_service_id()
                await filling_account_categories_by_category_id()

        return full_category
    return _factory

@pytest_asyncio.fixture
async def create_product_account(create_type_account_service, create_account_category):
    async def _factory(
            filling_redis: bool = True,
            type_account_service_id: int = None,
            account_category_id: int = None,
            hash_login: str = 'hash_login',
            hash_password: str = 'hash_password'
    ) -> ProductAccounts:
        async with get_db() as session_db:
            if type_account_service_id is None:
                service_type = await create_type_account_service(filling_redis=filling_redis)
                type_account_service_id = service_type.type_account_service_id
            if account_category_id is None:
                category = await create_account_category(filling_redis=filling_redis)
                account_category_id = category.account_category_id

            new_account = ProductAccounts(
                type_account_service_id = type_account_service_id,
                account_category_id = account_category_id,
                hash_login = hash_login,
                hash_password = hash_password
            )
            session_db.add(new_account)
            await session_db.commit()
            await session_db.refresh(new_account)

            if filling_redis:
                await filling_product_accounts_by_category_id()
                await filling_product_accounts_by_account_id()

        return new_account

    return _factory

@pytest_asyncio.fixture
async def create_sold_account(create_new_user, create_type_account_service):
    async def _factory(
            filling_redis: bool = True,
            owner_id: int = None,
            type_account_service_id: int = None,
            is_valid: bool = True,
            is_deleted: bool = False,
            hash_login: str = 'hash_login',
            hash_password: str = 'hash_password',
            language: str = "ru",
            name: str = "name",
            description: str = "description"
    ) -> SoldAccountsFull:
        async with get_db() as session_db:
            if owner_id is None:
                user = await create_new_user()
                owner_id = user.user_id
            if type_account_service_id is None:
                service = await create_type_account_service(filling_redis=filling_redis)
                type_account_service_id = service.type_account_service_id

            new_sold_account = SoldAccounts(
                owner_id = owner_id,
                type_account_service_id = type_account_service_id,
                is_valid = is_valid,
                is_deleted = is_deleted,
                hash_login = hash_login,
                hash_password = hash_password
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
                .options(selectinload(SoldAccounts.translations))
                .where(SoldAccounts.sold_account_id == new_sold_account.sold_account_id)
            )
            new_sold_account = result.scalar_one()

            full_account = SoldAccountsFull.from_orm_with_translation(new_sold_account, language)

        if filling_redis:
            await filling_sold_accounts_by_owner_id()
            await filling_sold_accounts_by_accounts_id()

        return full_account
    return _factory

@pytest_asyncio.fixture
async def create_ui_image(tmp_path, monkeypatch):
    """
    Factory: создаёт файл в tmp_path/media/ui_sections/<key>.png,
    подменяет MEDIA_DIR в модуле с функциями (чтобы get_ui_image видел файл),
    сохраняет запись UiImages в БД и возвращает (ui_image, abs_path).
    """
    async def _factory(key: str = "main_menu", show: bool = True, file_id: str = None):
        # Подготовим директорию и файл
        media_dir = tmp_path / "media"
        ui_sections = media_dir / "ui_sections"
        ui_sections.mkdir(parents=True, exist_ok=True)

        file_abs = ui_sections / f"{key}.png"
        file_abs.write_bytes(b"fake-image-bytes")       # создаём тестовый файл

        # Подменяем MEDIA_DIR в модуле с функциями (чтобы get_ui_image искал в tmp_path)
        import src.services.system.actions.actions as ser
        monkeypatch.setattr(ser, "MEDIA_DIR", str(media_dir))

        # Создаём запись в БД с относительным file_path
        from src.services.database.database import get_db

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

    return _factory