from datetime import datetime

from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import update, select

from src.bot_actions.bot_instance import get_bot_logger
from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.broker.producer import publish_event
from src.config import get_config
from src.services.database.users.actions import get_user, update_user
from src.services.database.users.models import UserAuditLogs, WalletTransaction, NotificationSettings
from src.services.database.core.database import get_db
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text
from src.services.database.referrals.actions import get_referral_lvl
from src.services.database.referrals.models.models_ref import Referrals, IncomeFromReferrals
from src.services.database.replenishments_event.schemas import ReplenishmentCompleted
from src.bot_actions.messages import send_log

async def referral_event_handler(event):
    payload = event["payload"]

    if event["event"] == "referral.new_referral":
        obj = ReplenishmentCompleted.model_validate(payload)
        await handler_new_income_referral(obj)

async def handler_new_income_referral(new_replenishment: ReplenishmentCompleted):
    money_credited = False
    last_lvl = 0
    current_lvl = 0
    percent_current_lvl = 0

    try:
        # проверка на повторную активацию
        async with get_db() as session_db:
            result_db = await session_db.execute(
                select(IncomeFromReferrals)
                .where(IncomeFromReferrals.replenishment_id == new_replenishment.replenishment_id)
            )
            income_ref = result_db.scalar_one_or_none()
            if income_ref:  # если обработали ранее, данное пополнение
                return

        async with get_db() as session_db:
            result = await session_db.execute(select(Referrals).where(Referrals.referral_id == new_replenishment.user_id))
            test_owner = result.scalar_one_or_none()
            if not test_owner:
                return
            else:
                last_lvl = test_owner.level

        owner = await get_user(test_owner.owner_user_id)

        referral_levels = await get_referral_lvl() # список отсортирован по возрастанию уровня
        for lvl in referral_levels:
            if new_replenishment.total_sum_replenishment >= lvl.amount_of_achievement: # если сумма пополнения больше или
                current_lvl = lvl.level
                percent_current_lvl = lvl.percent

        # обновление уровня
        if current_lvl:
            async with get_db() as session_db:
                await session_db.execute(
                    update(Referrals)
                    .where(Referrals.referral_id == new_replenishment.user_id)
                    .values(level=current_lvl)
                )
                await session_db.commit()

        # сумма начисления
        income_amount = int(new_replenishment.amount * percent_current_lvl / 100)
        if not income_amount:
            return

        owner = await update_user(
            user_id=owner.user_id,
            balance=owner.balance + income_amount,
            total_profit_from_referrals=owner.total_profit_from_referrals + income_amount,
        )

        # --- Создаём запись о доходе ---
        async with get_db() as session_db:
            new_income = IncomeFromReferrals(
                replenishment_id=new_replenishment.replenishment_id,
                owner_user_id=owner.user_id,
                referral_id=new_replenishment.user_id,
                amount=income_amount,
                percentage_of_replenishment=percent_current_lvl,
            )
            session_db.add(new_income)

            new_trans = WalletTransaction(
                user_id=owner.user_id,
                type='referral',
                amount=income_amount,
                balance_before=owner.balance - income_amount,
                balance_after=owner.balance
            )
            session_db.add(new_trans)

            await session_db.flush()
            new_log = UserAuditLogs(
                user_id=owner.user_id,
                action_type = 'profit from referral',
                message="Пользователь получил средства за пополнения от своего реферала",
                details={
                    "income_from_referral_id": new_income.income_from_referral_id,
                    "wallet_transaction_id": new_trans.wallet_transaction_id
                }
            )
            session_db.add(new_log)
            await session_db.commit()

            money_credited = True
            result_db = await session_db.execute(
                select(NotificationSettings)
                .where(NotificationSettings.user_id == owner.user_id)
            )
            notifications = result_db.scalar_one_or_none()
            if notifications and notifications.referral_replenishment:
                await on_referral_income_completed(
                    owner.user_id,
                    owner.language,
                    new_replenishment.amount,
                    last_lvl,
                    current_lvl,
                    percent_current_lvl
                )

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"#Ошибка_пополнения. Произошла ошибка при начислении денег владельцу реферала. "
                     f"Флаг обновлённого баланса: {money_credited}. Ошибка: {str(e)}.")
        await on_referral_income_failed(str(e))


async def on_referral_income_completed(user_id: int, language: str,  amount: int, last_lvl: int, current_lvl: int, percent: int):
    """Отсылает сообщение пользователю. Сообщение меняется в зависимости от изменения уровня реферала"""
    bot = await get_bot_logger()

    try:
        if last_lvl == current_lvl:  # если уровень у реферала не обновился
            message = get_text(
                language,
                "referral_messages",
                "referral_replenished_balance"
            ).format(level=current_lvl, amount=amount, percent=percent)
        else:
            message = get_text(
                language,
                "referral_messages",
                "referral_replenished_and_level_up"
            ).format(last_lvl=last_lvl, current_lvl=current_lvl, amount=amount, percent=percent)

        try:
            await bot.send_message(user_id, message)
        except TelegramForbiddenError:  # если бот заблокирован у пользователя
            pass
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception(
            f"#Ошибка_пополнения. Произошла ошибка при отсылке сообщения о пополнении денег владельцу реферала. Ошибка: {str(e)}."
        )

        event = EventSentLog(
            text=get_text(
                get_config().app.default_lang,
                "referral_messages",
                "log_replenishment_error"
            ).format(error=str(e), time=datetime.now().strftime(get_config().different.dt_format)),
            log_lvl=LogLevel.ERROR
        )
        await publish_event(event.model_dump(), "message.send_log")

async def on_referral_income_failed(error: str):
    """Отсылает лог ошибки при пополнении баланса"""
    event = EventSentLog(
        text=get_text(
            get_config().app.default_lang,
            "referral_messages",
            "log_replenishment_error"
        ).format(error=error, time=datetime.now().strftime(get_config().different.dt_format)),
        log_lvl=LogLevel.ERROR
    )
    await publish_event(event.model_dump(), "message.send_log")

