from datetime import datetime, timezone, timedelta

import pytest
from orjson import orjson
from sqlalchemy import delete, select, update

from src.config import PAGE_SIZE
from src.services.database.admins.models import AdminActions
from src.services.database.discounts.actions.actions_promo import get_promo_code_by_page, get_count_promo_codes, \
    deactivate_promo_code
from src.services.database.discounts.models import PromoCodes, Vouchers, VoucherActivations, ActivatedPromoCodes
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis
from src.services.database.discounts.models import SmallVoucher
from src.services.database.users.actions import get_user
from src.services.database.users.models import Users, WalletTransaction, UserAuditLogs
from src.utils.i18n import get_text

from tests.helpers.helper_functions import comparison_models
from tests.helpers.monkeypatch_data import fake_bot

@pytest.mark.asyncio
@pytest.mark.parametrize("use_redis", [True, False])
async def test_get_promo_code(use_redis, create_promo_code):
    from src.services.database.discounts.actions import get_promo_code
    if use_redis:
        async with get_db() as session_db:
            await session_db.execute(delete(PromoCodes))
            await session_db.commit()
    else:
        async with get_redis() as session_redis:
            await session_redis.flushdb()

    promo_code = await create_promo_code()
    promo = await get_promo_code(promo_code.activation_code)

    await comparison_models(promo_code, promo)

@pytest.mark.asyncio
async def test_get_promo_code_by_id(create_promo_code):
    from src.services.database.discounts.actions import get_promo_code
    promo_code = await create_promo_code()
    promo = await get_promo_code(promo_code_id=promo_code.promo_code_id)
    await comparison_models(promo_code, promo)


@pytest.mark.asyncio
@pytest.mark.parametrize("use_redis", [True, False])
async def test_get_valid_voucher_by_user_page(use_redis, create_new_user, create_voucher):
    from src.services.database.discounts.actions import get_valid_voucher_by_page
    user = await create_new_user()
    voucher_1 = await create_voucher(filling_redis=use_redis, creator_id=user.user_id)
    voucher_2 = await create_voucher(filling_redis=use_redis, creator_id=user.user_id)
    voucher_3 = await create_voucher(filling_redis=use_redis, creator_id=user.user_id)

    vouchers = await get_valid_voucher_by_page(user.user_id)

    assert SmallVoucher.from_orm_model(voucher_3) == vouchers[0]
    assert SmallVoucher.from_orm_model(voucher_2) == vouchers[1]
    assert SmallVoucher.from_orm_model(voucher_1) == vouchers[2]

@pytest.mark.asyncio
@pytest.mark.parametrize("use_redis", [True, False])
async def test_get_count_voucher(use_redis, create_new_user, create_voucher):
    from src.services.database.discounts.actions import get_count_voucher
    user = await create_new_user()
    voucher_1 = await create_voucher(filling_redis=use_redis, creator_id=user.user_id)
    voucher_2 = await create_voucher(filling_redis=use_redis, creator_id=user.user_id)

    counter = await get_count_voucher(user.user_id)
    assert counter == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("use_redis", [True, False])
async def test_get_valid_voucher_by_code(use_redis, create_voucher):
    from src.services.database.discounts.actions import get_valid_voucher_by_code
    voucher = await create_voucher(filling_redis=use_redis)
    voucher = await get_valid_voucher_by_code(voucher.activation_code)
    await comparison_models(voucher, voucher)

@pytest.mark.asyncio
async def test_get_voucher_by_id(create_voucher):
    from src.services.database.discounts.actions import get_voucher_by_id
    voucher = await create_voucher()
    voucher = await get_voucher_by_id(voucher.voucher_id)
    await comparison_models(voucher, voucher)

@pytest.mark.asyncio
async def test_create_promo_code(create_promo_code, create_new_user):
    from src.services.database.discounts.actions import create_promo_code as create_promo_code_for_test
    new_promo_code = await create_promo_code()
    new_promo_code.activation_code = 'unique_code'
    user = await create_new_user()

    promo_returned = await create_promo_code_for_test(
        creator_id=user.user_id,
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

        admin_action_db = await session_db.execute(
            select(AdminActions)
            .where(AdminActions.user_id == user.user_id)
        )
        assert admin_action_db.scalar_one()

    async with get_redis() as session_redis:
        promo_redis = orjson.loads(await session_redis.get(f'promo_code:{new_promo_code.activation_code}'))

    await comparison_models(new_promo_code, promo_returned, ['promo_code_id', 'start_at'])
    await comparison_models(promo_returned, promo_db)
    await comparison_models(promo_returned, promo_redis)


@pytest.mark.asyncio
async def test_create_voucher(create_voucher):
    from src.services.database.discounts.actions import create_voucher as create_voucher_for_test
    new_voucher = await create_voucher()

    async with get_db() as session_db:
        await session_db.execute(
            update(Users)
            .where(Users.user_id == new_voucher.creator_id)
            .values(balance = 10000)
        )
        await session_db.commit()

    voucher_returned = await create_voucher_for_test(
        user_id=new_voucher.creator_id,
        is_created_admin=new_voucher.is_created_admin,
        amount=new_voucher.amount,
        number_of_activations=new_voucher.number_of_activations,
        expire_at=new_voucher.expire_at
    )

    async with get_db() as session_db:
        result = await session_db.execute(select(Vouchers).where(Vouchers.voucher_id == voucher_returned.voucher_id))
        voucher = result.scalar_one_or_none()

        result = await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == new_voucher.creator_id))
        transfer = result.scalar_one_or_none()
        assert transfer
        assert transfer.amount == (new_voucher.amount * new_voucher.number_of_activations) * -1

    async with get_redis() as session_redis:
        voucher_redis = orjson.loads(await session_redis.get(f'voucher:{voucher_returned.activation_code}'))

    await comparison_models(new_voucher, voucher_returned, ['voucher_id', 'start_at', 'activation_code'])
    await comparison_models(voucher_returned, voucher)
    await comparison_models(voucher_returned, voucher_redis)


@pytest.mark.asyncio
class TestActivateVoucher:
    async def test_success_activation(self, create_voucher, create_new_user):
        """Пользователь успешно активирует ваучер"""
        from src.services.database.discounts.actions import activate_voucher

        user = await create_new_user()
        origin_balance = user.balance
        voucher = await create_voucher()

        result_message, success = await activate_voucher(user, voucher.activation_code, user.language)

        async with get_db() as session_db:
            result = await session_db.execute(
                select(VoucherActivations)
                .where(VoucherActivations.voucher_id == voucher.voucher_id)
            )
            assert result.scalar_one_or_none()

        expected = get_text(
            user.language,
            'discount',
            "Voucher successfully activated! \n\nVoucher amount: {amount} \nCurrent balance: {new_balance}"
        ).format(amount=voucher.amount, new_balance= origin_balance + voucher.amount)

        assert result_message == expected
        assert success == True

    async def test_voucher_not_found(self, create_new_user):
        """Ваучера с таким кодом нет"""
        from src.services.database.discounts.actions import activate_voucher

        user = await create_new_user()

        result_message, success = await activate_voucher(user, "INVALIDCODE", user.language)

        expected = get_text(
            user.language,
            'discount',
            "Voucher with this code not found")
        assert result_message == expected

    async def test_voucher_already_activated(self, create_voucher, create_new_user):
        """Пользователь не может активировать один и тот же ваучер дважды"""
        from src.services.database.discounts.actions import activate_voucher

        user = await create_new_user()
        voucher = await create_voucher()

        async with get_db() as session_db:
            new_activate = VoucherActivations(
                voucher_id = voucher.voucher_id,
                user_id = user.user_id
            )
            session_db.add(new_activate)
            await session_db.commit()

        # пробуем активировать ваучер который уже активирован ранее этим пользователем
        result_message, success = await activate_voucher(user, voucher.activation_code, user.language)

        expected = get_text(
            user.language,
            'discount',
            "You have already activated this voucher. It can only be activated once"
        )
        assert result_message == expected
        assert success == False

    async def test_voucher_expired_by_time(self, create_new_user):
        """Ваучер просрочен по времени"""
        from src.services.database.discounts.actions import activate_voucher
        owner_voucher = await create_new_user()
        user = await create_new_user()

        # создаём просроченный ваучер
        expired_voucher = Vouchers(
            creator_id=owner_voucher.user_id,
            activation_code="EXPIREDCODE",
            amount=100,
            activated_counter=0,
            number_of_activations=5,
            expire_at=datetime.now(timezone.utc) - timedelta(days=1),
            is_valid=True,
        )

        async with get_db() as session:
            session.add(expired_voucher)
            await session.commit()
            await session.refresh(expired_voucher)

        result_message, success = await activate_voucher(user, expired_voucher.activation_code, user.language)

        expected = get_text(
            user.language,
            'discount',
            "Voucher expired \n\nID '{id}' \nCode '{code}' \n\nVoucher expired due to time limit. It can no longer be activated"
        ).format(id=expired_voucher.voucher_id, code=expired_voucher.activation_code)

        assert result_message == expected
        assert success == False

    async def test_voucher_activate_owner(self, create_new_user, create_voucher):
        """Пытаемся активировать ваучер когда тот кто пытается - его владелец"""
        from src.services.database.discounts.actions import activate_voucher
        voucher = await create_voucher()
        user = await get_user(voucher.creator_id)

        result_message, success = await activate_voucher(user, voucher.activation_code, user.language)

        expected = get_text(
            user.language,
            'discount',
            "You cannot activate the voucher. You are its creator")
        assert result_message == expected
        assert success == False


@pytest.mark.asyncio
class TestDeactivateVoucher:

    @pytest.mark.asyncio
    async def test_admin_voucher_no_refund(self, create_voucher):
        """Если ваучер создан админом — возврата нет"""
        from src.services.database.discounts.actions import deactivate_voucher

        voucher = await create_voucher()
        voucher.is_created_admin = True
        voucher.voucher_id = 2

        async with get_db() as session_db:
            session_db.add(voucher)
            await session_db.commit()

        result = await deactivate_voucher(voucher.voucher_id)

        async with get_redis() as session_redis:
            result_redis = await session_redis.get(f"voucher:{voucher.activation_code}")
            assert not result_redis


        assert result == 0 # не должны вернутся деньги

    async def test_with_refund(self, create_voucher):
        """Корректный возврат денег пользователю + удаление из Redis"""
        from src.services.database.discounts.actions import deactivate_voucher

        voucher = await create_voucher()
        returned_money = voucher.amount * voucher.number_of_activations # сколько денег должно вернутся
        result = await deactivate_voucher(voucher.voucher_id)
        assert result == returned_money

        async with get_db() as session_db:
            result_db_user = await session_db.execute(select(Users).where(Users.user_id == voucher.creator_id))
            result_db_transaction = await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == voucher.creator_id))
            result_db_log = await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == voucher.creator_id))

            user: Users = result_db_user.scalar_one_or_none()
            transaction: WalletTransaction = result_db_transaction.scalar_one_or_none()
            result_db_log = result_db_log.scalars().all()

            assert user.balance == returned_money
            assert transaction.type == "refund"
            assert len(result_db_log) == 2, "должно быть два лога"

        async with get_redis() as session_redis:
            result_redis = await session_redis.get(f"voucher:{voucher.activation_code}")
            assert not result_redis

            result_redis = await session_redis.get(f"voucher_by_user:{voucher.creator_id}")
            assert not orjson.loads(result_redis)

            user_from__redis = orjson.loads(await session_redis.get(f"user:{voucher.creator_id}"))
            assert user_from__redis['balance'] == returned_money


@pytest.mark.asyncio
async def test_get_promo_code_by_page(create_promo_code):
    promo_codes = []
    for i in range(10):
        promo_codes.append((await create_promo_code()).to_dict())

    result_pomo_code = await get_promo_code_by_page(page=1)

    for i in range(PAGE_SIZE):
        assert result_pomo_code[i].to_dict() in  promo_codes


@pytest.mark.asyncio
async def test_get_count_promo_codes(create_promo_code):
    for i in range(10):
        await create_promo_code()

    quantity_promo = await get_count_promo_codes()
    assert quantity_promo == 10


@pytest.mark.asyncio
async def test_set_not_valid_promo_code(create_settings):
    """Проверяем, что _set_not_valid_promo_code деактивирует только истёкшие промокоды"""
    from src.services.database.discounts.utils.set_not_valid import _set_not_valid_promo_code

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

    # проверка лога (должен быть только при деактивации промокода)
    message_log = get_text(
        'ru',
        'discount',
        "#Promo_code_expired \nID '{id}' \nCode '{code}'"
        "\n\nThe promo code has expired due to reaching the number of activations or time limit. It is no longer possible to activate it"
    ).format(id=expired_promo.promo_code_id, code=expired_promo.activation_code)
    assert fake_bot.get_message(create_settings.channel_for_logging_id, message_log)


@pytest.mark.asyncio
async def test_check_activate_promo_code(create_promo_code, create_new_user):
    from src.services.database.discounts.actions import check_activate_promo_code
    user = await create_new_user()
    promo_code = await create_promo_code()

    async with get_db() as session_db:
        activated = ActivatedPromoCodes(
            promo_code_id=promo_code.promo_code_id,
            user_id=user.user_id
        )
        session_db.add(activated)
        await session_db.commit()

    assert  await check_activate_promo_code(promo_code.promo_code_id, user.user_id)


@pytest.mark.asyncio
async def test_deactivate_promo_code(create_promo_code, create_new_user):
    user = await create_new_user()
    promo = await create_promo_code()

    await deactivate_promo_code(user.user_id, promo.promo_code_id)

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(PromoCodes)
            .where(PromoCodes.promo_code_id == promo.promo_code_id)
        )
        update_promo = result_db.scalar_one_or_none()
        assert update_promo.is_valid == False

    async with get_redis() as session_redis:
        assert not await session_redis.get(f"promo_code:{promo.promo_code_id}")

