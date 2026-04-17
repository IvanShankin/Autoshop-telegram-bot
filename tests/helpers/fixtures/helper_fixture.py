from typing import AsyncGenerator, Any

import aiohttp
import fakeredis
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.fake_moduls.fake_rebbit_mq_producer import FakeRabbitMQProducer
from src.models.read_models import UsersDTO, ProductAccountFull
from tests.helpers.fake_moduls.fake_tg_account_client import FakeTelegramAccountClient
from tests.helpers.func_fabrics.fake_objects_fabric import crypto_provider_factory, secret_storage_factory
from src.config import get_config, init_config
from src.containers import init_request_container, RequestContainer
from tests.helpers.func_fabrics.other_fabric import create_purchase_request_fabric, create_balance_holder_factory
from tests.helpers.func_fabrics import create_new_user_fabric, create_admin_fabric, create_referral_fabric, \
    create_income_from_referral_fabric, create_replenishment_fabric, create_type_payment_factory, \
    create_voucher_factory, create_category_factory, create_account_storage_factory, \
    create_product_account_factory, create_sold_account_factory, create_ui_image_factory, \
    create_wallet_transaction_fabric, create_tg_account_media_factory, create_promo_codes_fabric, \
    create_sent_mass_message_fabric, create_purchase_fabric, create_transfer_moneys_fabric, \
    create_promo_code_activation_fabric, create_backup_log_fabric, create_translate_category_factory, \
    create_universal_storage_factory, create_product_universal_factory, create_sold_universal_factory
from src.database.models.categories import ProductType, AccountServiceType, StorageStatus, UniversalMediaType, \
    ProductAccounts
from src.database.models.system import Settings
from src.database.models.system.models import ReplenishmentService
from src.database import get_session_factory
from src.infrastructure.crypto_bot.core import CryptoBotProvider
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace


@pytest_asyncio.fixture
async def session_db_fix() -> AsyncSession:
    async_session_factory = get_config().db_connection.session_local

    async with async_session_factory() as session_db:
        yield session_db


@pytest_asyncio.fixture
async def fake_tg_client():
    class FakeTgClient:
        pass

    return FakeTgClient()


@pytest_asyncio.fixture
async def crypto_bot_provider_fix():
    class FakeCryptoBotClient:
        async def create_invoice(self, amount, payload, expires_in):
            return SimpleNamespace(invoice_id="inv", bot_invoice_url="url")

    yield CryptoBotProvider(FakeCryptoBotClient())


@pytest_asyncio.fixture()
async def secret_storage_fix():
    return secret_storage_factory()


@pytest_asyncio.fixture
async def crypto_provider_fix():
    return crypto_provider_factory()


@pytest_asyncio.fixture
async def container_fix(
    fake_tg_client,
    session_db_fix,
    crypto_bot_provider_fix,
    crypto_provider_fix,
    secret_storage_fix,
    get_secret_fix,
) -> AsyncGenerator[RequestContainer, Any]:
    async def fake_support_kb(*args, **kwargs) -> None:
        pass

    http_session = aiohttp.ClientSession()
    config = init_config(get_secret_fix.execute)

    container = init_request_container(
        session_db=session_db_fix,
        session_redis=fakeredis.aioredis.FakeRedis(),
        config=config,
        http_session=http_session,
        telegram_client=fake_tg_client,
        telegram_logger_client=fake_tg_client,
        crypto_bot_provider=crypto_bot_provider_fix,
        crypto_provider=crypto_provider_fix,
        secret_storage=secret_storage_fix,
        producer=FakeRabbitMQProducer(),
        support_kb_builder=fake_support_kb,
        telegram_account_client=FakeTelegramAccountClient(),
    )
    yield container


@pytest_asyncio.fixture
async def create_new_user(container_fix):
    """ Создаст нового пользователя в БД"""
    async def _factory(
        user_name: str = "test_username",
        union_ref_code: str = None,
        balance: int = 0,
        total_sum_replenishment: int = 0,
        filling_redis: bool = True
    ) -> UsersDTO:
        return await create_new_user_fabric(
            container_fix=container_fix,
            user_name=user_name,
            union_ref_code=union_ref_code,
            balance=balance,
            total_sum_replenishment=total_sum_replenishment,
            filling_redis=filling_redis,
        )

    return _factory


@pytest_asyncio.fixture
async def create_admin_fix(container_fix: RequestContainer):
    async def _factory(
        filling_redis: bool = True,
        user_id: int | None = None,
    ):
        return await create_admin_fabric(
            container_fix=container_fix,
            filling_redis=filling_redis,
            user_id=user_id,
        )

    return _factory


@pytest_asyncio.fixture
async def create_sent_mass_message(container_fix: RequestContainer):
    async def _factory(
        admin_id: int | None = None,
        content: str = "content",
        photo_path: str = "photo_path",
        button_url: str = "https://example.com",
        number_received: int = 10,
        number_sent: int = 10,
    ):
        return await create_sent_mass_message_fabric(
            container_fix=container_fix,
            admin_id=admin_id,
            content=content,
            photo_path=photo_path,
            button_url=button_url,
            number_received=number_received,
            number_sent=number_sent,
        )

    return _factory


@pytest_asyncio.fixture
async def create_referral(container_fix: RequestContainer):
    """
    Создаёт тестовый реферала (у нового пользователя появляется владелец)
    :return Реферал(Referrals), Владельца(Users) и Реферала(Users)
    """
    async def _factory(
        owner_id: int | None = None,
        referral_id: int | None = None,
    ):
        return await create_referral_fabric(
            container_fix=container_fix,
            owner_id=owner_id,
            referral_id=referral_id,
        )

    return _factory


@pytest_asyncio.fixture
async def create_income_from_referral(container_fix: RequestContainer):
    """
    Создаёт доход от реферала, если не указать реферала, то создаст нового, если не указать владельца, то создаст нового.
    :return Доход(IncomeFromReferrals), Реферал(Users), Владелец(Users)
    """
    async def _factory(
        referral_user_id: int | None = None,
        owner_id: int | None = None,
        replenishment_id: int | None = None,
        amount: int = 100,
        percentage_of_replenishment: int = 5,
    ):
        return await create_income_from_referral_fabric(
            container_fix=container_fix,
            referral_user_id=referral_user_id,
            owner_id=owner_id,
            replenishment_id=replenishment_id,
            amount=amount,
            percentage_of_replenishment=percentage_of_replenishment,
        )

    return _factory


@pytest_asyncio.fixture
async def create_replenishment(container_fix: RequestContainer):
    """Создаёт пополнение для пользователя"""
    async def _factory(
        amount: int = 110,
        user_id: int | None = None,
        status: str = "completed",
    ):
        return await create_replenishment_fabric(
            container_fix=container_fix,
            amount=amount,
            user_id=user_id,
            status=status,
        )

    return _factory


@pytest_asyncio.fixture
async def create_type_payment(container_fix: RequestContainer):
    """Создаст новый тип оплаты в БД"""
    async def _factory(
        filling_redis: bool = True,
        name_for_user: str | None = None,
        service: ReplenishmentService | None = None,
        is_active: bool | None = None,
        commission: float | None = None,
        index: int | None = None,
        extra_data: dict | None = None,
    ):
        return await create_type_payment_factory(
            container_fix=container_fix,
            filling_redis=filling_redis,
            name_for_user=name_for_user,
            service=service,
            is_active=is_active,
            commission=commission,
            index=index,
            extra_data=extra_data,
        )

    return _factory


@pytest_asyncio.fixture(autouse=True)
async def create_settings() -> Settings:
    settings = Settings(
        support_username='support_username',
        channel_for_logging_id=123456789,
        channel_for_subscription_id=987654321,
        FAQ='FAQ'
    )
    async with get_session_factory() as session_db:
        session_db.add(settings)
        await session_db.commit()
        await session_db.refresh(settings)

    return settings


@pytest_asyncio.fixture
async def create_promo_code(container_fix: RequestContainer):
    """Создаст новый промокод в БД и в _redis."""
    async def _factory(
        activation_code: str = "TESTCODE",
        min_order_amount: int = 100,
        amount: int = 100,
        discount_percentage: int | None = None,
        number_of_activations: int = 5,
        expire_at: datetime = datetime.now(timezone.utc) + timedelta(days=1),
        is_valid: bool = True,
    ):
        return await create_promo_codes_fabric(
            container_fix=container_fix,
            activation_code=activation_code,
            min_order_amount=min_order_amount,
            amount=amount,
            discount_percentage=discount_percentage,
            number_of_activations=number_of_activations,
            expire_at=expire_at,
            is_valid=is_valid,
        )

    return _factory


@pytest_asyncio.fixture
async def create_promo_code_activation(container_fix: RequestContainer):
    """Создаст новый промокод в БД и в _redis."""
    async def _factory(
        promo_code_id: int | None = None,
        user_id: int | None = None,
    ):
        return await create_promo_code_activation_fabric(
            container_fix=container_fix,
            promo_code_id=promo_code_id,
            user_id=user_id,
        )

    return _factory


@pytest_asyncio.fixture
async def create_voucher(container_fix: RequestContainer):
    async def _factory(
        filling_redis: bool = True,
        creator_id: int | None = None,
        expire_at: datetime = datetime.now(timezone.utc) + timedelta(days=1),
        is_valid: bool = True,
        is_created_admin: bool = False,
        number_of_activations: int = 5,
    ):
        return await create_voucher_factory(
            container_fix=container_fix,
            filling_redis=filling_redis,
            creator_id=creator_id,
            expire_at=expire_at,
            is_valid=is_valid,
            is_created_admin=is_created_admin,
            number_of_activations=number_of_activations,
        )

    return _factory


@pytest_asyncio.fixture
async def create_translate_category(container_fix: RequestContainer):
    async def _factory(
        category_id: int,
        filling_redis: bool = True,
        language: str = "ru",
        name: str = "name",
        description: str = "description",
    ):
        return await create_translate_category_factory(
            container_fix=container_fix,
            category_id=category_id,
            filling_redis=filling_redis,
            language=language,
            name=name,
            description=description,
        )

    return _factory


@pytest_asyncio.fixture
async def create_category(container_fix: RequestContainer):
    async def _factory(
        filling_redis: bool = True,
        parent_id: int | None = None,
        ui_image_key: str | None = None,
        index: int | None = None,
        show: bool = True,
        is_main: bool = True,
        is_product_storage: bool = False,
        allow_multiple_purchase: bool = False,
        product_type: str = ProductType.ACCOUNT,
        type_account_service: AccountServiceType = AccountServiceType.TELEGRAM,
        reuse_product: bool = False,
        price: int = 150,
        cost_price: int = 100,
        language: str = "ru",
        name: str = "name",
        description: str = "description",
    ):
        return await create_category_factory(
            container_fix=container_fix,
            filling_redis=filling_redis,
            parent_id=parent_id,
            ui_image_key=ui_image_key,
            index=index,
            show=show,
            is_main=is_main,
            is_product_storage=is_product_storage,
            allow_multiple_purchase=allow_multiple_purchase,
            product_type=product_type,
            type_account_service=type_account_service,
            reuse_product=reuse_product,
            price=price,
            cost_price=cost_price,
            language=language,
            name=name,
            description=description,
        )

    return _factory


@pytest_asyncio.fixture
async def create_purchase(container_fix: RequestContainer):
    async def _factory(
        user_id: int | None = None,
        product_type: ProductType | None = None,
        account_storage_id: int | None = None,
        universal_storage_id: int | None = None,
        original_price: int = 110,
        purchase_price: int = 100,
        cost_price: int = 50,
        net_profit: int = 50,
    ):
        return await create_purchase_fabric(
            container_fix=container_fix,
            user_id=user_id,
            product_type=product_type,
            account_storage_id=account_storage_id,
            universal_storage_id=universal_storage_id,
            original_price=original_price,
            purchase_price=purchase_price,
            cost_price=cost_price,
            net_profit=net_profit,
        )

    return _factory


@pytest_asyncio.fixture
async def create_account_storage(container_fix: RequestContainer):
    async def _factory(
        is_active: bool = True,
        is_valid: bool = True,
        is_file: bool = True,
        status: StorageStatus = StorageStatus.FOR_SALE,
        type_account_service: AccountServiceType = AccountServiceType.TELEGRAM,
        phone_number: str = '+7 920 107-42-12',
    ):
        return await create_account_storage_factory(
            container_fix=container_fix,
            is_active=is_active,
            is_valid=is_valid,
            is_file=is_file,
            status=status,
            type_account_service=type_account_service,
            phone_number=phone_number,
        )

    return _factory


@pytest_asyncio.fixture
async def create_product_account(container_fix: RequestContainer):
    async def _factory(
        filling_redis: bool = True,
        type_account_service: AccountServiceType = AccountServiceType.TELEGRAM,
        category_id: int | None = None,
        account_storage_id: int | None = None,
        status: StorageStatus = StorageStatus.FOR_SALE,
        phone_number: str = '+7 920 107-42-12',
        price: int = 150,
    ) -> (ProductAccounts, ProductAccountFull):
        return await create_product_account_factory(
            container_fix=container_fix,
            filling_redis=filling_redis,
            type_account_service=type_account_service,
            category_id=category_id,
            account_storage_id=account_storage_id,
            status=status,
            phone_number=phone_number,
            price=price,
        )

    return _factory


@pytest_asyncio.fixture
async def create_sold_account(container_fix: RequestContainer):
    async def _factory(
        filling_redis: bool = True,
        owner_id: int | None = None,
        type_account_service: AccountServiceType = AccountServiceType.TELEGRAM,
        account_storage_id: int | None = None,
        is_active: bool = True,
        is_valid: bool = True,
        language: str = "ru",
        name: str = "name",
        description: str = "description",
        phone_number: str = "+7 920 107-42-12",
    ):
        return await create_sold_account_factory(
            container_fix=container_fix,
            filling_redis=filling_redis,
            owner_id=owner_id,
            type_account_service=type_account_service,
            account_storage_id=account_storage_id,
            is_active=is_active,
            is_valid=is_valid,
            language=language,
            name=name,
            description=description,
            phone_number=phone_number,
        )

    return _factory


@pytest_asyncio.fixture
async def create_tg_account_media(container_fix: RequestContainer):
    async def _factory(
        account_storage_id: int | None = None,
        tdata_tg_id: str | None = None,
        session_tg_id: str | None = None,
    ):
        return await create_tg_account_media_factory(
            container_fix=container_fix,
            account_storage_id=account_storage_id,
            tdata_tg_id=tdata_tg_id,
            session_tg_id=session_tg_id,
        )

    return _factory


@pytest_asyncio.fixture
async def create_universal_storage(container_fix: RequestContainer):
    async def _factory(
        media_type: UniversalMediaType = UniversalMediaType.DOCUMENT,
        original_filename: str | None = True,
        is_active: bool = True,
        language: str = "ru",
        name: str = "Universal product name",
        description: str = "Universal product description",
        encrypted_tg_file_id: str | None = "fb3425dh12hbf34bfd5dh7sjg5f",
        encrypted_tg_file_id_nonce: str | None = None,
        checksum: str = "checksum",
        key_version: int = 1,
        encryption_algo: str = "AES-GCM-256",
        status: StorageStatus = StorageStatus.FOR_SALE,
    ):
        return await create_universal_storage_factory(
            container_fix=container_fix,
            media_type=media_type,
            original_filename=original_filename,
            is_active=is_active,
            language=language,
            name=name,
            description=description,
            encrypted_tg_file_id=encrypted_tg_file_id,
            encrypted_tg_file_id_nonce=encrypted_tg_file_id_nonce,
            checksum=checksum,
            key_version=key_version,
            encryption_algo=encryption_algo,
            status=status,
        )

    return _factory


@pytest_asyncio.fixture
async def create_product_universal(container_fix: RequestContainer):
    async def _factory(
        filling_redis: bool = True,
        universal_storage_id: int | None = None,
        encrypted_tg_file_id_nonce: str | None = None,
        status: StorageStatus = StorageStatus.FOR_SALE,
        category_id: int | None = None,
        language: str = "ru",
    ):
        return await create_product_universal_factory(
            container_fix=container_fix,
            filling_redis=filling_redis,
            universal_storage_id=universal_storage_id,
            encrypted_tg_file_id_nonce=encrypted_tg_file_id_nonce,
            status=status,
            category_id=category_id,
            language=language,
        )

    return _factory


@pytest_asyncio.fixture
async def create_sold_universal(container_fix: RequestContainer):
    async def _factory(
        filling_redis: bool = True,
        owner_id: int | None = None,
        universal_storage_id: int | None = None,
        is_active: bool = True,
        language: str = "ru",
    ):
        return await create_sold_universal_factory(
            container_fix=container_fix,
            filling_redis=filling_redis,
            owner_id=owner_id,
            universal_storage_id=universal_storage_id,
            is_active=is_active,
            language=language,
        )

    return _factory


@pytest_asyncio.fixture
async def create_ui_image(container_fix: RequestContainer):
    """
    сохраняет запись UiImages в БД и возвращает (ui_image, abs_path).
    """
    async def _factory(
        key: str = "main_menu",
        show: bool = True,
        file_id: str | None = None,
    ):
        return await create_ui_image_factory(
            container_fix=container_fix,
            key=key,
            show=show,
            file_id=file_id,
        )

    return _factory


@pytest_asyncio.fixture
async def create_transfer_moneys(container_fix: RequestContainer):
    async def _factory(
        user_from_id: int | None = None,
        user_where_id: int | None = None,
        amount: int = 100,
    ):
        return await create_transfer_moneys_fabric(
            container_fix=container_fix,
            user_from_id=user_from_id,
            user_where_id=user_where_id,
            amount=amount,
        )

    return _factory


@pytest_asyncio.fixture
async def create_wallet_transaction(container_fix: RequestContainer):
    async def _factory(
        user_id: int | None = None,
        type: str = 'replenish',
        amount: int = 100,
    ):
        return await create_wallet_transaction_fabric(
            container_fix=container_fix,
            user_id=user_id,
            type=type,
            amount=amount,
        )

    return _factory


@pytest_asyncio.fixture
async def create_backup_log(container_fix: RequestContainer):
    async def _factory(
        storage_file_name: str | None = None,
        storage_encrypted_dek_name: str | None = None,
        encrypted_dek_b64: str = "encrypted_dek_b64",
        dek_nonce_b64: str = "dek_nonce_b64",
        size_bytes: int = 12345,
    ):
        return await create_backup_log_fabric(
            container_fix=container_fix,
            storage_file_name=storage_file_name,
            storage_encrypted_dek_name=storage_encrypted_dek_name,
            encrypted_dek_b64=encrypted_dek_b64,
            dek_nonce_b64=dek_nonce_b64,
            size_bytes=size_bytes,
        )

    return _factory


@pytest_asyncio.fixture
async def create_purchase_request(container_fix: RequestContainer):
    async def _factory(
        user_id: int | None = None,
        promo_code_id: int | None = None,
        quantity: int = 1,
        total_amount: int = 100,
        status: str = 'processing',
    ):
        return await create_purchase_request_fabric(
            container_fix=container_fix,
            user_id=user_id,
            promo_code_id=promo_code_id,
            quantity=quantity,
            total_amount=total_amount,
            status=status,
        )

    return _factory


@pytest_asyncio.fixture
async def create_balance_holder(container_fix: RequestContainer):
    async def _factory(
        purchase_request_id: int | None = None,
        user_id: int | None = None,
        amount: int = 100,
        status: str = 'held',
    ):
        return await create_balance_holder_factory(
            container_fix=container_fix,
            purchase_request_id=purchase_request_id,
            user_id=user_id,
            amount=amount,
            status=status,
        )

    return _factory