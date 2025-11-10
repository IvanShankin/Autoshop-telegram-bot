from datetime import datetime, timezone, timedelta

import orjson
import pytest_asyncio
from tests.helpers.func_fabric import create_new_user_fabric, create_admin_fabric, create_referral_fabric, \
    create_income_from_referral_fabric, create_replenishment_fabric, create_type_payment_factory, \
    create_voucher_factory, create_type_account_service_factory, create_account_service_factory, \
    create_translate_account_category_factory, create_account_category_factory, create_account_storage_factory, \
    create_product_account_factory, create_sold_account_factory, create_ui_image_factory, \
    create_wallet_transaction_fabric, create_tg_account_media_factory
from src.services.redis.core_redis import get_redis
from src.services.database.discounts.models import PromoCodes
from src.services.database.system.models import  Settings
from src.services.database.core.database import get_db


@pytest_asyncio.fixture
async def create_new_user():
    """ Создаст нового пользователя в БД"""
    return create_new_user_fabric

@pytest_asyncio.fixture
async def create_admin_fix(create_new_user):
    return create_admin_fabric

@pytest_asyncio.fixture
async def create_referral(create_new_user):
    """
    Создаёт тестовый реферала (у нового пользователя появляется владелец)
    :return Реферал(Referrals), Владельца(Users) и Реферала(Users)
    """
    return create_referral_fabric

@pytest_asyncio.fixture
async def create_income_from_referral(create_new_user, create_replenishment):
    """
    Создаёт доход от реферала, если не указать реферала, то создаст нового, если не указать владельца, то создаст нового.
    :return Доход(IncomeFromReferrals), Реферал(Users), Владелец(Users)
    """
    return create_income_from_referral_fabric

@pytest_asyncio.fixture
async def create_replenishment(create_new_user):
    """Создаёт пополнение для пользователя"""
    return create_replenishment_fabric


@pytest_asyncio.fixture
async def create_type_payment():
    """Создаст новый тип оплаты в БД"""
    return create_type_payment_factory


@pytest_asyncio.fixture(autouse=True)
async def create_settings() -> Settings:
    settings = Settings(
        support_username='support_username',
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
async def create_voucher(create_new_user):
    return create_voucher_factory


@pytest_asyncio.fixture
async def create_type_account_service():
    return create_type_account_service_factory


@pytest_asyncio.fixture
async def create_account_service(create_type_account_service):
    return create_account_service_factory


@pytest_asyncio.fixture
async def create_translate_account_category():
    return create_translate_account_category_factory


@pytest_asyncio.fixture
async def create_account_category(create_account_service, create_ui_image):
    return create_account_category_factory


@pytest_asyncio.fixture
async def create_account_storage(create_type_account_service, create_account_category):
    return create_account_storage_factory


@pytest_asyncio.fixture
async def create_product_account(create_type_account_service, create_account_category, create_account_storage):
    return create_product_account_factory


@pytest_asyncio.fixture
async def create_sold_account(create_new_user, create_type_account_service, create_account_storage):
    return create_sold_account_factory


@pytest_asyncio.fixture
async def create_tg_account_media(create_new_user, create_type_account_service, create_account_storage):
    return create_tg_account_media_factory


@pytest_asyncio.fixture
async def create_ui_image(tmp_path, monkeypatch):
    """
    сохраняет запись UiImages в БД и возвращает (ui_image, abs_path).
    """
    return create_ui_image_factory


@pytest_asyncio.fixture
async def create_wallet_transaction(create_new_user):
    return create_wallet_transaction_fabric
