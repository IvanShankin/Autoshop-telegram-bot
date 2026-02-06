import orjson
import pytest
from sqlalchemy import select

from src.services.database.core.database import get_db
from src.services.database.replenishments_event.schemas import ReplenishmentCompleted
from src.services.database.users.models import Users, WalletTransaction, UserAuditLogs
from src.services.redis.core_redis import get_redis
from src.utils.i18n import get_text
from tests.helpers.helper_functions import comparison_models
from tests.helpers.monkeypatch_data import fake_bot


@pytest.mark.asyncio
async def test_handler_new_income_referral(
    create_referral,
    create_replenishment
):
    """Проверяем корректную работу handler_new_income_referral"""
    from src.services.database.referrals.events import handler_new_income_referral
    from src.services.database.referrals.actions import get_referral_lvl
    from src.services.database.referrals.models import IncomeFromReferrals, Referrals

    _, owner, referral = await create_referral()
    replenishment = await create_replenishment(amount = 999999)

    initial_balance = owner.balance
    initial_total_profit = owner.total_profit_from_referrals

    # --- создаём событие ---
    event = ReplenishmentCompleted(
        user_id = referral.user_id,
        replenishment_id = replenishment.replenishment_id,
        amount = replenishment.amount,
        total_sum_replenishment = referral.total_sum_replenishment + replenishment.amount,
        error = False,
        error_str = '',
        language = 'ru',
        username = referral.username
    )

    await handler_new_income_referral(event)

    async with get_db() as session_db:
        # проверка пользователя (владельца реферала)
        user_result = await session_db.execute(
            select(Users).where(Users.user_id == owner.user_id)
        )
        updated_user = user_result.scalar_one()

        assert updated_user.balance > initial_balance, "Баланс не увеличился"
        assert updated_user.total_profit_from_referrals > initial_total_profit, "Суммарная прибыль от рефералов не обновилась"

        # проверка уровня в Referrals
        referral_result = await session_db.execute(
            select(Referrals).where(Referrals.referral_id == referral.user_id)
        )
        updated_ref = referral_result.scalar_one()
        assert updated_ref.level >= 0, "Уровень реферала не обновился"

        # проверка IncomeFromReferrals
        income_result = await session_db.execute(
            select(IncomeFromReferrals)
            .where(IncomeFromReferrals.owner_user_id == owner.user_id)
        )
        income = income_result.scalars().first()
        assert income.amount > 0, "Запись о доходе от рефералов не создана"
        assert income.percentage_of_replenishment > 0, "Процент не сохранился"

        # проверка WalletTransaction
        wallet_result = await session_db.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == owner.user_id)
        )
        wallet_trans = wallet_result.scalars().first()
        assert wallet_trans.type == "referral", "Неверный тип транзакции"
        assert wallet_trans.amount == income.amount, "Сумма транзакции не совпадает"
        assert wallet_trans.balance_after == updated_user.balance, "Баланс после транзакции некорректен"

        # проверка UserAuditLogs
        log_result = await session_db.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == owner.user_id)
        )
        log = log_result.scalars().first()
        assert log.action_type == "profit from referral", "Неверный action_type в логах"

    # проверка Redis
    async with get_redis() as session_redis:
        redis_data = orjson.loads(await session_redis.get(f"user:{owner.user_id}"))

    assert comparison_models(updated_user, redis_data)

    # --- проверяем, что пользователю ушло сообщение ---
    percent = None
    ref_lvl = await get_referral_lvl()
    for lvl in ref_lvl:
        if updated_ref.level == lvl.level:
            percent = lvl.percent

    expected_message = get_text(
        owner.language,
        "referral_messages",
        "referral_replenished_and_level_up"
    ).format(last_lvl=1, current_lvl=updated_ref.level,  amount=replenishment.amount, percent=percent)

    assert fake_bot.get_message(owner.user_id, expected_message), "Сообщение о доходе от реферала не отправлено"

@pytest.mark.asyncio
async def test_on_referral_income_completed_no_level_up():
    """Проверяет сообщение без повышения уровня (last_lvl == current_lvl)"""
    from src.services.database.referrals.events import on_referral_income_completed
    user_id = 101
    language = "ru"
    amount = 50
    last_lvl = 2
    current_lvl = 2
    percent = 10

    await on_referral_income_completed(user_id, language, amount, last_lvl, current_lvl, percent)

    message = get_text(
        language,
        "referral_messages",
        "referral_replenished_balance"
    ).format(level=current_lvl, amount=amount, percent=percent)

    assert fake_bot.check_str_in_messages(message[:100]), "Сообщение о пополнении без повышения уровня не отправлено"


@pytest.mark.asyncio
async def test_on_referral_income_completed_with_level_up():
    """Проверяет сообщение с повышением уровня (last_lvl != current_lvl)"""
    from src.services.database.referrals.events import on_referral_income_completed
    user_id = 202
    language = "ru"
    amount = 100
    last_lvl = 1
    current_lvl = 2
    percent = 15

    await on_referral_income_completed(user_id, language, amount, last_lvl, current_lvl, percent)

    message = get_text(
        language,
        "referral_messages",
        "referral_replenished_and_level_up"
    ).format(last_lvl=last_lvl, current_lvl=current_lvl, amount=amount, percent=percent)

    assert fake_bot.check_str_in_messages(message[:100]), "Сообщение о пополнении с повышением уровня не отправлено"

