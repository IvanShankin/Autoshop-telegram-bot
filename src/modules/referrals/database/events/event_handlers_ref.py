from sqlalchemy import update

from src.database.action_core_models import get_user, update_user
from src.database.models_main import UserAuditLogs, WalletTransaction
from src.database.database import get_db
from src.modules.referrals.database.actions_ref import get_referral_lvl
from src.modules.referrals.database.events.schemas_ref import NewIncomeFromRef
from src.modules.referrals.database.models_ref import Referrals, IncomeFromReferrals


async def referral_event_handler(event):
    if isinstance(event, NewIncomeFromRef):
        await handler_new_income_referral(event)

async def handler_new_income_referral(new_replenishment: NewIncomeFromRef):
    """Сюда попадаем если владелец у реферала точно есть"""
    new_level = 0
    percent_current_lvl = 0
    owner = await get_user(new_replenishment.owner_id)

    referral_levels = await get_referral_lvl() # список отсортирован по возрастанию уровня
    for lvl in referral_levels:
        if new_replenishment.total_sum_replenishment >= lvl.amount_of_achievement: # если сумма пополнения больше или
            new_level = lvl.level
            percent_current_lvl = lvl.percent

    # обновление уровня
    if new_level:
        async with get_db() as session_db:
            await session_db.execute(
                update(Referrals)
                .where(Referrals.referral_id == new_replenishment.referral_id)
                .values(level=new_level)
            )
            await session_db.commit()

    # сумма начисления
    income_amount = int(new_replenishment.amount * percent_current_lvl / 100)
    if not income_amount:
        return

    owner.balance = owner.balance + income_amount
    owner.total_profit_from_referrals = owner.total_profit_from_referrals + income_amount

    await update_user(owner)

    # --- Создаём запись о доходе ---
    async with get_db() as session_db:
        new_income = IncomeFromReferrals(
            replenishment_id=new_replenishment.replenishment_id,
            owner_user_id=new_replenishment.owner_id,
            referral_id=new_replenishment.referral_id,
            amount=income_amount,
            percentage_of_replenishment=percent_current_lvl,
        )

        new_trans = WalletTransaction(
            user_id=new_replenishment.owner_id,
            type='referral',
            amount=income_amount,
            balance_before=owner.balance - income_amount,
            balance_after=owner.balance
        )

        new_log = UserAuditLogs(
            user_id=new_replenishment.owner_id,
            action_type = 'profit from referral'
        )
        session_db.add(new_income)
        session_db.add(new_trans)
        session_db.add(new_log)
        await session_db.commit()
