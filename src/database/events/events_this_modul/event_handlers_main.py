from datetime import datetime

from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select, update
from sqlalchemy.orm import object_session

from src.config import DT_FORMAT_FOR_LOGS
from src.database.action_core_models import update_user, get_user
from src.database.models_main import WalletTransaction, UserAuditLogs, Replenishments
from src.database.database import get_db
from src.database.events.core_event import push_deferred_event
from src.database.events.events_this_modul.schemas_main import NewReplenishment
from src.i18n import get_i18n
from src.bot_instance import bot
from src.modules.keyboard_main import support_kb
from src.modules.referrals.database.events.schemas_ref import NewIncomeFromRef
from src.modules.referrals.database.models_ref import Referrals
from src.utils.core_logger import logger
from src.utils.send_messages import send_log


async def user_event_handler(event):
    """Обрабатывает event запуская определённую функцию"""
    if isinstance(event, NewReplenishment):
        await handler_new_replenishment(event)

async def handler_new_replenishment(new_replenishment: NewReplenishment):
    """Обрабатывает создание нового пополнения у пользователя"""
    money_credited = False # флаг начисления денег (только для ошибки)
    i18n = get_i18n('ru', 'replenishment_dom')
    language = 'ru'
    username = "None"

    try:
        user = await get_user(new_replenishment.user_id)
        language = user.language
        username = user.username
        user.balance = user.balance + new_replenishment.amount
        user.total_sum_replenishment = user.total_sum_replenishment + new_replenishment.amount

        i18n = get_i18n(user.language, 'replenishment_dom')

        updated_user = await update_user(user)
        money_credited = True

        async with get_db() as session_db:
            await session_db.execute(
                update(Replenishments)
                .where(Replenishments.replenishment_id == new_replenishment.replenishment_id)
                .values(status="completed")
            )

            # обновление связанных таблиц
            new_wallet_transaction = WalletTransaction(
                user_id = new_replenishment.user_id,
                type = 'replenish',
                amount = new_replenishment.amount,
                balance_before = updated_user.balance - new_replenishment.amount,
                balance_after = updated_user.balance ,
            )
            new_log = UserAuditLogs(
                user_id = new_replenishment.user_id,
                action_type = 'replenish',
                details = {'amount': new_replenishment.amount,'new_balance': updated_user.balance }
            )

            session_db.add(new_wallet_transaction)
            session_db.add(new_log)
            await session_db.commit()

            result_db = await session_db.execute(select(Referrals).where(Referrals.referral_id == updated_user.user_id))
            referral = result_db.scalar_one_or_none()

            # если пользователь чей-то реферал, то запустим событие NewReplenishment
            if referral:
                session = object_session(NewReplenishment)  # Определяет объект сессии которая в данный момент управляет NewReplenishment
                if session:
                    # откладываем событие
                    push_deferred_event(
                        session,
                        NewIncomeFromRef(
                            referral_id=updated_user.user_id,
                            replenishment_id=new_replenishment.replenishment_id,
                            owner_id=referral.owner_user_id,
                            amount=new_replenishment.amount,
                            total_sum_replenishment=updated_user.total_sum_replenishment
                        )
                    )

            # отсылка успеха
            message_success = i18n.ngettext(
                "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
                "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
                new_replenishment.amount
            ).format(sum=new_replenishment.amount)

            try:
                await bot.send_message(updated_user.user_id, message_success)
            except TelegramForbiddenError: # если бот заблокирован
                pass

            message_log = i18n.ngettext(
                "#Replenishment \n\nUser @{username} successfully topped up the balance by {sum} ruble. \nReplenishment ID: {replenishment_id}",
                "#Replenishment \n\nUser @{username} successfully topped up the balance by {sum} rubles. \nReplenishment ID: {replenishment_id}",
                new_replenishment.amount
            ).format(username=user.username, sum=new_replenishment.amount, replenishment_id=new_replenishment.replenishment_id)

            await send_log(message_log)
    except Exception as e:
        new_status_replenishment = 'error'
        logger.error(
            f"#Ошибка_пополнения Произошла ошибка при пополнении. "
            f"Флаг обновлённого баланса: {money_credited}. "
            f"ID пополнения: {new_replenishment.replenishment_id}. "
            f"Ошибка: {str(e)}"
        )

        if money_credited: # если сумма поступила
            message_for_user = i18n.ngettext(
                "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
                "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
                new_replenishment.amount
            ).format(sum=new_replenishment.amount)
            await bot.send_message(new_replenishment.user_id, message_for_user)

            message_log = i18n.gettext(
                "#Replenishment_error \n\nUser @{username} Paid money, balance updated, but an error occurred inside the server. \n"
                "Replenishment ID: {replenishment_id}.\nError: {error} \n\nTime: {time}"
            ).format(
                username=username,
                replenishment_id=new_replenishment.replenishment_id,
                error=str(e),
                time=datetime.now().strftime(DT_FORMAT_FOR_LOGS)
            )

            new_status_replenishment = "completed"
        else:
            message_for_user = i18n.gettext(
                "An error occurred while replenishing!\nReplenishment ID: {replenishment_id} "
                "\n\nWe apologize for the inconvenience. \nPlease contact support."
            ).format(replenishment_id=new_replenishment.replenishment_id)
            await bot.send_message(new_replenishment.user_id, message_for_user, reply_markup=await support_kb(language))

            message_log = i18n.gettext(
                "#Replenishment_error \n\nUser @{username} Paid money, but the balance was not updated. \n"
                "Replenishment ID: {replenishment_id}. \nError: {error} \n\nTime: {time}"
            ).format(
                username=username,
                replenishment_id=new_replenishment.replenishment_id,
                error=str(e),
                time=datetime.now().strftime(DT_FORMAT_FOR_LOGS)
            )

            new_status_replenishment = "error"

        # обновляем БД
        try:
            async with get_db() as session_db:
                await session_db.execute(
                    update(Replenishments)
                    .where(Replenishments.replenishment_id == new_replenishment.replenishment_id)
                    .values(status=new_status_replenishment)
                )
        except Exception as e:
            logger.error(f"Не удалось обновить данные о новом пополнении. Ошибка: {str(e)}")
            await send_log(f"Не удалось обновить данные о новом пополнении. \nОшибка: {str(e)}")

        await send_log(message_log)
