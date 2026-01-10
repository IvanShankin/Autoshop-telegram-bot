import pytest_asyncio

from tests.helpers.func_fabric import create_new_user_fabric, create_admin_fabric, create_referral_fabric, \
    create_income_from_referral_fabric, create_replenishment_fabric, create_type_payment_factory, \
    create_voucher_factory, create_category_factory, create_account_storage_factory, \
    create_product_account_factory, create_sold_account_factory, create_ui_image_factory, \
    create_wallet_transaction_fabric, create_tg_account_media_factory, create_promo_codes_fabric, \
    create_sent_mass_message_fabric, create_purchase_account_fabric, create_transfer_moneys_fabric, \
    create_promo_code_activation_fabric, create_backup_log_fabric, create_translate_category_factory, \
    create_product_factory
from src.services.database.system.models import  Settings
from src.services.database.core.database import get_db



@pytest_asyncio.fixture
async def create_new_user():
    """ Создаст нового пользователя в БД"""
    return create_new_user_fabric


@pytest_asyncio.fixture
async def create_admin_fix():
    return create_admin_fabric


@pytest_asyncio.fixture
async def create_sent_mass_message():
    return create_sent_mass_message_fabric


@pytest_asyncio.fixture
async def create_referral():
    """
    Создаёт тестовый реферала (у нового пользователя появляется владелец)
    :return Реферал(Referrals), Владельца(Users) и Реферала(Users)
    """
    return create_referral_fabric


@pytest_asyncio.fixture
async def create_income_from_referral():
    """
    Создаёт доход от реферала, если не указать реферала, то создаст нового, если не указать владельца, то создаст нового.
    :return Доход(IncomeFromReferrals), Реферал(Users), Владелец(Users)
    """
    return create_income_from_referral_fabric


@pytest_asyncio.fixture
async def create_replenishment():
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
async def create_promo_code():
    """Создаст новый промокод в БД и в redis."""
    return create_promo_codes_fabric


@pytest_asyncio.fixture
async def create_promo_code_activation():
    """Создаст новый промокод в БД и в redis."""
    return create_promo_code_activation_fabric


@pytest_asyncio.fixture
async def create_voucher():
    return create_voucher_factory


@pytest_asyncio.fixture
async def create_translate_category():
    return create_translate_category_factory


@pytest_asyncio.fixture
async def create_category():
    return create_category_factory


@pytest_asyncio.fixture
async def create_account_storage():
    return create_account_storage_factory


@pytest_asyncio.fixture
async def create_product():
    return create_product_factory


@pytest_asyncio.fixture
async def create_product_account():
    return create_product_account_factory


@pytest_asyncio.fixture
async def create_purchase_account():
    return create_purchase_account_fabric


@pytest_asyncio.fixture
async def create_sold_account():
    return create_sold_account_factory


@pytest_asyncio.fixture
async def create_tg_account_media():
    return create_tg_account_media_factory


@pytest_asyncio.fixture
async def create_ui_image():
    """
    сохраняет запись UiImages в БД и возвращает (ui_image, abs_path).
    """
    return create_ui_image_factory


@pytest_asyncio.fixture
async def create_transfer_moneys():
    return create_transfer_moneys_fabric


@pytest_asyncio.fixture
async def create_wallet_transaction():
    return create_wallet_transaction_fabric


@pytest_asyncio.fixture
async def create_backup_log():
    return create_backup_log_fabric