import orjson
import pytest

from src.services.redis.filling import filling_voucher_by_user_id, filling_types_payments_by_id, \
    filling_all_types_payments, filling_user, filling_vouchers, filling_promo_code, \
    filling_banned_accounts, filling_admins
from tests.helpers.helper_functions import comparison_models
from src.services.database.discounts.models import SmallVoucher
from src.services.database.users.models import  BannedAccounts
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis


class TestFillRedisSingleObjects():
    """Тесты для заполнения Redis одиночными объектами"""

    @pytest.mark.asyncio
    async def test_filling_admins(self, create_new_user, create_admin_fix):
        user = await create_new_user(user_name="admin_user", union_ref_code = "admin_ref")
        admin = await create_admin_fix(filling_redis=False, user_id=user.user_id)

        await filling_admins()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"admin:{user.user_id}")

        assert val

    @pytest.mark.asyncio
    async def test_filling_banned_accounts(self, create_new_user):
        user = await create_new_user(user_name="banned_user", union_ref_code = "banned_ref")
        banned = BannedAccounts(user_id=user.user_id, reason="test ban")
        async with get_db() as session_db:
            session_db.add(banned)
            await session_db.commit()


        await filling_banned_accounts()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"banned_account:{user.user_id}")

        assert val


    @pytest.mark.asyncio
    async def test_filling_promo_code(self, create_promo_code):
        promo_code = await create_promo_code()

        await filling_promo_code()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"promo_code:{promo_code.activation_code}")

        assert comparison_models(promo_code.to_dict(), orjson.loads(val))

    @pytest.mark.asyncio
    async def test_filling_vouchers(self, create_new_user, create_voucher):
        user = await create_new_user()
        voucher = await create_voucher(filling_redis=False, creator_id=user.user_id)

        await filling_vouchers()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"voucher:{voucher.activation_code}")

        assert comparison_models(voucher.to_dict(), orjson.loads(val))


@pytest.mark.asyncio
async def test_filling_user(create_new_user):
    user = await create_new_user()
    await filling_user(user)

    async with get_redis() as session_redis:
        user_redis = await session_redis.get(f'user:{user.user_id}')
        assert comparison_models(user, orjson.loads(user_redis))


@pytest.mark.asyncio
async def test_filling_all_types_payments(create_type_payment):
    type_payment_1 = await create_type_payment(filling_redis=False, name_for_user="name_2", index=1)
    type_payment_0 = await create_type_payment(filling_redis=False, name_for_user="name_1", index=0)
    type_payment_2 = await create_type_payment(filling_redis=False, name_for_user="name_1", index=2)

    await filling_all_types_payments()

    async with get_redis() as session_redis:
        value = await session_redis.get("all_types_payments")
        assert value
        all_types = orjson.loads(value)

    # проверяем правильность фильтрации по индексу
    assert type_payment_0.to_dict() == all_types[0]
    assert type_payment_1.to_dict() == all_types[1]
    assert type_payment_2.to_dict() == all_types[2]


@pytest.mark.asyncio
async def test_filling_types_payments_by_id(create_type_payment):
    type_payment_1 = await create_type_payment(filling_redis=False, name_for_user="name_1")

    await filling_types_payments_by_id(type_payment_1.type_payment_id)

    async with get_redis() as session_redis:
        value = await session_redis.get(f"type_payments:{type_payment_1.type_payment_id}")
        assert value
        type_payment = orjson.loads(value)

    assert type_payment == type_payment_1.to_dict()


@pytest.mark.asyncio
async def test_filling_voucher_by_user_id(create_new_user, create_voucher):
    user = await create_new_user()
    voucher_1 = await create_voucher(filling_redis=False, creator_id=user.user_id)
    voucher_2 = await create_voucher(filling_redis=False, creator_id=user.user_id)
    voucher_3 = await create_voucher(filling_redis=False, creator_id=user.user_id)

    await filling_voucher_by_user_id(user.user_id)

    async with get_redis() as session_redis:
        value = await session_redis.get(f"voucher_by_user:{user.user_id}")
        assert value
        vouchers = orjson.loads(value)

        # проверяем сортировку по дате создания (desc)
        assert SmallVoucher.from_orm_model(voucher_1).model_dump() == vouchers[2]
        assert SmallVoucher.from_orm_model(voucher_2).model_dump() == vouchers[1]
        assert SmallVoucher.from_orm_model(voucher_3).model_dump() == vouchers[0]
