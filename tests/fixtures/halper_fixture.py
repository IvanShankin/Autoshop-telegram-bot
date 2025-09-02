import pytest_asyncio
from src.database.core_models import Users, TypePayments
from src.database.database import get_db


@pytest_asyncio.fixture
async def create_new_user()->dict:
    """
    Создаст нового пользователя в БД
    :return:
    dict{
        user_id: int,
        username: str,
        language: str,
        unique_referral_code: str,
        balance: int,
        total_sum_replenishment: int,
        total_profit_from_referrals: int,
        created_at: DateTime(timezone=True)
    }
    """
    new_user = Users(
        username="test_username",
        unique_referral_code="test_referral_code",
    )
    async with get_db() as session_db:
        session_db.add(new_user)
        await session_db.commit()
        await session_db.refresh(new_user)

    return new_user.to_dict()



@pytest_asyncio.fixture
async def create_type_payment() -> dict:
    """
    Создаст новый тип оплаты в БД
    :return:
    dict{
        type_payment_id: int,
        name_for_user: str,
        name_for_admin: str,
        is_active: bool,
        commission: float,
        extra_data: Optional[dict]
    }
    """
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

    return new_type_payment.to_dict()

