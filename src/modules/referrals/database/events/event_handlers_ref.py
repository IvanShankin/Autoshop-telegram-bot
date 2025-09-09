from sqlalchemy import update, select
from twisted.internet.defer import execute

from src.database.action_main_models import get_user, update_user
from src.database.models_main import UserAuditLogs, WalletTransaction, NotificationSettings
from src.database.database import get_db
from src.modules.referrals.database.actions_ref import get_referral_lvl
from src.modules.referrals.database.models_ref import Referrals, IncomeFromReferrals
from src.services.replenishments.schemas import ReplenishmentCompleted
from src.utils.core_logger import logger


async def referral_event_handler(event):
    if isinstance(event, ReplenishmentCompleted):
        await handler_new_income_referral(event)

async def handler_new_income_referral(new_replenishment: ReplenishmentCompleted):
    money_credited = False
    new_level = 0 # тут додумать
    try:
        async with get_db() as session_db:
            result = await session_db.execute(select(Referrals).where(Referrals.referral_id == new_replenishment.user_id))
            test_owner = result.scalar_one_or_none()
            if not test_owner:
                return

        new_level = 0
        percent_current_lvl = 0
        owner = await get_user(test_owner.owner_user_id)

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
                    .where(Referrals.referral_id == new_replenishment.user_id)
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
                owner_user_id=owner.user_id,
                referral_id=new_replenishment.user_id,
                amount=income_amount,
                percentage_of_replenishment=percent_current_lvl,
            )

            new_trans = WalletTransaction(
                user_id=owner.user_id,
                type='referral',
                amount=income_amount,
                balance_before=owner.balance - income_amount,
                balance_after=owner.balance
            )

            new_log = UserAuditLogs(
                user_id=owner.user_id,
                action_type = 'profit from referral'
            )
            session_db.add(new_income)
            session_db.add(new_trans)
            session_db.add(new_log)
            await session_db.commit()

            money_credited = True
            result_db = await session_db.execute(
                select(NotificationSettings)
                .where(NotificationSettings.user_id == owner.user_id)
            )
            notifications = result_db.scalar_one_or_none()
            if notifications and notifications.referral_replenishment:
                await on_referral_income_completed()


    except Exception as e:
        logger.error("#")
        await on_referral_income_failed()


async def on_referral_income_completed():
    pass
    # передать сюда всё что необходимо для пользовтателя
    # только отправляем только успешные сообщения пользователю

async def on_referral_income_failed():
    pass
    # только отправляем только лог если не удалось и возникла ошибка

