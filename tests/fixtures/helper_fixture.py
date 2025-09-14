from datetime import datetime, timezone, timedelta

import orjson
import pytest_asyncio
from sqlalchemy import select

from src.redis_dependencies.core_redis import get_redis
from src.services.discounts.models import PromoCodes
from src.services.users.models import Users, Replenishments, NotificationSettings
from src.services.system.models import TypePayments, Settings
from src.services.database.database import get_db
from src.services.referrals.models import Referrals


@pytest_asyncio.fixture
async def create_new_user()->Users:
    """
    Создаст нового пользователя в БД
    :return: Users
    """
    new_user = Users(
        username="test_username",
        unique_referral_code="test_referral_code",
    )
    async with get_db() as session_db:
        session_db.add(new_user)
        await session_db.commit()
        await session_db.refresh(new_user)

        new_notifications = NotificationSettings(
            user_id=new_user.user_id
        )
        session_db.add(new_notifications)
        await session_db.commit()

    return new_user


@pytest_asyncio.fixture
async def create_referral(create_new_user)->(Referrals, Users, Users):
    """
    Создаёт тестовый реферала (у нового пользователя появляется владелец)
    :return Владельца и Реферала
    """
    async with get_db() as session_db:
        # создаём владельца
        owner = Users(
            username="owner_user",
            language="ru",
            unique_referral_code="owner_code_123",
            balance=0,
            total_sum_replenishment=0,
            total_profit_from_referrals=0,
        )
        session_db.add(owner)
        await session_db.commit()
        await session_db.refresh(owner)

        new_notifications = NotificationSettings(
            user_id=owner.user_id
        )
        session_db.add(new_notifications)
        await session_db.commit()

        # связываем реферала и владельца
        referral = Referrals(
            referral_id=create_new_user.user_id,
            owner_user_id=owner.user_id,
            level=0,
        )
        session_db.add(referral)
        await session_db.commit()
        await session_db.refresh(referral)

    return owner, create_new_user


@pytest_asyncio.fixture
async def create_replenishment(create_new_user)-> Replenishments:
    """Создаёт пополнение для пользователя"""
    async with get_db() as session_db:
        # создаём тип платежа (если ещё нет)
        result = await session_db.execute(select(TypePayments))
        type_payment = result.scalars().first()
        if not type_payment:
            type_payment = TypePayments(
                name_for_user="TestPay",
                name_for_admin="TestPayAdmin",
                commission=0.0,
            )
            session_db.add(type_payment)
            await session_db.commit()
            await session_db.refresh(type_payment)

        repl = Replenishments(
            user_id=create_new_user.user_id,
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
async def create_type_payment() -> TypePayments:
    """Создаст новый тип оплаты в БД"""
    new_type_payment = TypePayments(
        name_for_user="Test Payment Method",
        name_for_admin="Test Payment Method (Admin)",
        is_active=True,
        commission=5,
        extra_data={"api_key": "test_key", "wallet_id": "test_wallet"}
    )
    async with get_db() as session_db:
        session_db.add(new_type_payment)
        await session_db.commit()
        await session_db.refresh(new_type_payment)

    return new_type_payment


@pytest_asyncio.fixture
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
