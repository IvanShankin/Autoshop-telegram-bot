from datetime import datetime

from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import update, select

from src.utils.bot_instance import get_bot
from src.config import DT_FORMAT_FOR_LOGS
from src.services.users.actions import get_user, update_user
from src.services.users.models import UserAuditLogs, WalletTransaction, NotificationSettings
from src.services.database.database import get_db
from src.utils.i18n import get_i18n
from src.services.referrals.actions import get_referral_lvl
from src.services.referrals.models.models_ref import Referrals, IncomeFromReferrals
from src.services.replenishments_event.schemas import ReplenishmentCompleted
from src.utils.core_logger import logger
from src.utils.send_messages import send_log


async def referral_event_handler(event):
    if isinstance(event, ReplenishmentCompleted):
        await handler_new_income_referral(event)

async def handler_new_income_referral(new_replenishment: ReplenishmentCompleted):
    money_credited = False
    last_lvl = 0
    current_lvl = 0
    percent_current_lvl = 0

    try:
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
                await on_referral_income_completed(
                    owner.user_id,
                    owner.language,
                    new_replenishment.amount,
                    last_lvl,
                    current_lvl,
                    percent_current_lvl
                )

    except Exception as e:
        logger.error(f"#Ошибка_пополнения. Произошла ошибка при начислении денег владельцу реферала. "
                     f"Флаг обновлённого баланса: {money_credited}. Ошибка: {str(e)}.")
        await on_referral_income_failed(str(e))


async def on_referral_income_completed(user_id: int, language: str,  amount: int, last_lvl: int, current_lvl: int, percent: int):
    """Отсылает сообщение пользователю. Сообщение меняется в зависимости от изменения уровня реферала"""
    bot = get_bot()

    try:
        i18n = get_i18n(language, "replenishment_dom")
        if last_lvl == current_lvl:  # если уровень у реферала не обновился
            message = i18n.gettext(
                "💸 Your referral has replenished the balance. \n💡 Referral level: {level} \n💵 You have earned {amount}₽ ({percent}%)\n\n"
                "• Funds have been credited to your balance in your personal account."
            ).format(level=current_lvl, amount=amount, percent=percent)
        else:
            message = i18n.gettext(
                "💸 Your referral has replenished their balance and increased the level of the referral system.\n"
                "🌠 Referral level: {last_lvl} ➡️ {current_lvl}\n"
                "💰 You have earned: {amount}₽ ({percent}%)\n\n"
                "• Funds have been credited to your balance in your personal account."
            ).format(last_lvl=last_lvl, current_lvl=current_lvl, amount=amount, percent=percent)

        try:
            await bot.send_message(user_id, message)
        except TelegramForbiddenError:  # если бот заблокирован у пользователя
            pass
    except Exception as e:
        logger.error(
            f"#Ошибка_пополнения. Произошла ошибка при отсылке сообщения о пополнении денег владельцу реферала. Ошибка: {str(e)}."
        )

        i18n = get_i18n('ru', "replenishment_dom")
        message_log = i18n.gettext(
            "#Replenishment_error \n\n"
            "An error occurred while sending a message about replenishing funds to the referral owner. \n"
            "Error: {error}. \n\n"
            "Time: {time}"
        ).format(error=str(e), time=datetime.now().strftime(DT_FORMAT_FOR_LOGS))
        await send_log(message_log)

async def on_referral_income_failed(error: str):
    """Отсылает лог ошибки при пополнении баланса"""
    i18n = get_i18n('ru', "replenishment_dom")
    message_log = i18n.gettext(
        "#Replenishment_error \n\n"
        "An error occurred while sending a message about replenishing funds to the referral owner. \n"
        "Error: {error}. \n\n"
        "Time: {time}"
    ).format(error=error, time=datetime.now().strftime(DT_FORMAT_FOR_LOGS))

    await send_log(message_log)

