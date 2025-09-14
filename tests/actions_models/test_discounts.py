from datetime import datetime, timezone, timedelta

import pytest
from orjson import orjson
from sqlalchemy import delete, select

from src.services.discounts.models import PromoCodes
from src.services.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.helper_fixture import  create_promo_code
from tests.fixtures.helper_functions import comparison_models
from tests.fixtures.monkeypatch_data import replacement_fake_bot, replacement_fake_keyboard, fake_bot, replacement_exception_aiogram

@pytest.mark.asyncio
@pytest.mark.parametrize("use_redis", [True, False])
async def test_get_valid_promo_code(use_redis, create_promo_code):
    from src.services.discounts.actions import get_valid_promo_code
    if use_redis:
        async with get_db() as session_db:
            await session_db.execute(delete(PromoCodes))
            await session_db.commit()
    else:
        async with get_redis() as session_redis:
            await session_redis.flushdb()


    promo = await get_valid_promo_code(create_promo_code.activation_code)

    await comparison_models(create_promo_code, promo)

@pytest.mark.asyncio
async def test_create_promo_code(create_promo_code):
    from src.services.discounts.actions import create_promo_code as create_promo_code_for_test
    new_promo_code = create_promo_code
    new_promo_code.activation_code = 'unique_code'

    promo_returned = await create_promo_code_for_test(
        code=new_promo_code.activation_code,
        min_order_amount=new_promo_code.min_order_amount,
        amount=new_promo_code.amount,
        discount_percentage=new_promo_code.discount_percentage,
        number_of_activations=new_promo_code.number_of_activations,
        expire_at=new_promo_code.expire_at
    )

    async with get_db() as session_db:
        result = await session_db.execute(select(PromoCodes).where(PromoCodes.promo_code_id == promo_returned.promo_code_id))
        promo_db = result.scalar_one_or_none()

    async with get_redis() as session_redis:
        promo_redis = orjson.loads(await session_redis.get(f'promo_code:{new_promo_code.activation_code}'))

    await comparison_models(new_promo_code, promo_returned, ['promo_code_id', 'start_at'])
    await comparison_models(promo_returned, promo_db)
    await comparison_models(promo_returned, promo_redis)




@pytest.mark.asyncio
async def test_set_not_valid_promo_code(
    replacement_fake_bot,
    replacement_fake_keyboard,
    replacement_exception_aiogram,
):
    """Проверяем, что _set_not_valid_promo_code деактивирует только истёкшие промокоды"""
    from src.services.discounts.actions import _set_not_valid_promo_code

    now = datetime.now(timezone.utc)
    expired_promo = PromoCodes(
        activation_code="TESTCODE_1",
        min_order_amount=100,
        amount=100,
        discount_percentage=None,
        number_of_activations=5,
        expire_at= now - timedelta(seconds=5),
        is_valid=True,
    )
    active_promo = PromoCodes(
        activation_code="TESTCODE_2",
        min_order_amount=100,
        amount=100,
        discount_percentage=None,
        number_of_activations=5,
        expire_at=now + timedelta(days=1),
        is_valid=True,
    )

    async with get_db() as session_db:
        session_db.add(expired_promo)
        session_db.add(active_promo)
        await session_db.commit()

    await _set_not_valid_promo_code()

    # проверка состояния в БД
    async with get_db() as session_db:
        result = await session_db.execute(select(PromoCodes).where(PromoCodes.promo_code_id == expired_promo.promo_code_id))
        expired_from_db = result.scalar_one_or_none()
        assert expired_from_db.is_valid is False

        result = await session_db.execute(select(PromoCodes).where(PromoCodes.promo_code_id == active_promo.promo_code_id))
        active_from_db = result.scalar_one_or_none()
        assert active_from_db.is_valid is True