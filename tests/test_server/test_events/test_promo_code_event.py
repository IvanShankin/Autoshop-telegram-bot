import pytest
from sqlalchemy import select, update

from src.services.database.core.database import get_db
from src.services.database.discounts.events import handler_new_activate_promo_code
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
@pytest.mark.parametrize('should_become_inactive',[True, False])
async def test_handler_new_activate_promo_code(
    should_become_inactive,
    create_promo_code,
    create_new_user,
    create_settings,
):
    from src.services.database.discounts.events.schemas import NewActivatePromoCode
    from src.services.database.discounts.models import PromoCodes, ActivatedPromoCodes
    promo_code = await create_promo_code()
    old_promo = promo_code
    if should_become_inactive: # сделаем поромокод на одну активацию
        async with get_db() as session_db:
            await session_db.execute(
                update(PromoCodes)
                .where(PromoCodes.promo_code_id == promo_code.promo_code_id)
                .values(number_of_activations=1)
            )
            await session_db.commit()
            promo_code.number_of_activations = 1

    user = await create_new_user()
    settings = create_settings

    event = NewActivatePromoCode(
        promo_code_id = old_promo.promo_code_id,
        user_id = user.user_id
    )

    await handler_new_activate_promo_code(event)

    async with get_db() as session_db:
        result = await session_db.execute(
            select(ActivatedPromoCodes)
            .where(
                (ActivatedPromoCodes.promo_code_id == old_promo.promo_code_id) &
                (ActivatedPromoCodes.user_id == user.user_id)
            )
        )
        activate = result.scalar_one_or_none()
        assert activate

        result = await session_db.execute(select(PromoCodes).where(PromoCodes.promo_code_id == promo_code.promo_code_id))
        promo = result.scalar_one_or_none()

        assert promo.activated_counter == old_promo.activated_counter + 1
        if should_become_inactive: # если промокод был на одну активацию, то должен стать невалидным
            assert promo.is_valid == False
        else:
            assert promo.is_valid == True

        async with get_redis() as session_redis:
            redis_result = await session_redis.get(f"promo_code:{old_promo.activation_code}")

            if should_become_inactive: # если промокод был на одну активацию, то должен удалиться с redis
                assert not redis_result
            else:
                assert redis_result


