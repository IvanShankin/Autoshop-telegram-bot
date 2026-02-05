from datetime import datetime
from sqlalchemy import update, select

from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.broker.producer import publish_event
from src.config import get_config
from src.services.database.users.actions import update_user, get_user
from src.services.database.users.models import WalletTransaction, UserAuditLogs, Replenishments
from src.services.database.core.database import get_db
from src.services.database.replenishments_event.schemas import NewReplenishment
from src.utils.i18n import  get_text, n_get_text
from src.modules.keyboard_main import support_kb
from src.services.database.replenishments_event.schemas import ReplenishmentCompleted, ReplenishmentFailed
from src.utils.core_logger import get_logger
from src.bot_actions.messages import send_message


async def replenishment_event_handler(event):
    payload = event["payload"]

    if event["event"] == "replenishment.new_replenishment":
        obj = NewReplenishment.model_validate(payload)
        await handler_new_replenishment(obj)


async def handler_new_replenishment(new_replenishment: NewReplenishment):
    """Обрабатывает создание нового пополнения у пользователя"""
    money_credited = False # флаг начисления денег
    error = True
    language = 'ru'
    username = "None"
    error_str = None
    total_sum_replenishment = None

    try:
        # защита от повторных обработок
        async with get_db() as session_db:
            replenishment_db = await session_db.execute(
                select(Replenishments)
                .where(Replenishments.replenishment_id == new_replenishment.replenishment_id)
            )
            replenishment: Replenishments = replenishment_db.scalar_one_or_none()
            if not replenishment or replenishment.status != 'processing':
                return

        user = await get_user(new_replenishment.user_id)
        user.balance = user.balance + new_replenishment.amount
        user.total_sum_replenishment = user.total_sum_replenishment + new_replenishment.amount

        language = user.language
        username = get_text(language, 'profile_messages', 'No') if user.username is None else f'@{user.username}'
        total_sum_replenishment = user.total_sum_replenishment

        updated_user = await update_user(
            user_id=user.user_id,
            balance=user.balance,
            total_sum_replenishment=user.total_sum_replenishment
        )
        money_credited = True

        async with get_db() as session_db:
            await session_db.execute(
                update(Replenishments)
                .where(Replenishments.replenishment_id == new_replenishment.replenishment_id)
                .values(status="completed")
            )

            # обновление связанных таблиц
            new_wallet_transaction = WalletTransaction(
                user_id=new_replenishment.user_id,
                type='replenish',
                amount=new_replenishment.amount,
                balance_before=updated_user.balance - new_replenishment.amount,
                balance_after=updated_user.balance ,
            )
            new_log = UserAuditLogs(
                user_id=new_replenishment.user_id,
                action_type='replenish',
                message="Пользователь пополнили баланс",
                details={
                    "replenishment_id": new_replenishment.replenishment_id,
                    "wallet_transaction_id": new_wallet_transaction.wallet_transaction_id,
                    "amount": new_replenishment.amount,
                    "new_balance": updated_user.balance
                }
            )

            session_db.add(new_wallet_transaction)
            session_db.add(new_log)
            await session_db.commit()

        error = False
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(
            f"\n#Ошибка_пополнения Произошла ошибка при пополнении 'handler_new_replenishment'. \n"
            f"Флаг обновлённого баланса: {money_credited}. \n"
            f"ID пополнения: {new_replenishment.replenishment_id}. \n"
            f"Ошибка: {str(e)} "
        )
        error_str = str(e)

        if money_credited: # если сумма поступила
            new_status_replenishment = "completed"
        else:
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
            logger.exception(f"Не удалось обновить данные о новом пополнении. Ошибка: {str(e)}")
            event = EventSentLog(text=f"Не удалось обновить данные о новом пополнении. Ошибка: {str(e)}")
            await publish_event(event.model_dump(), "message.send_log")

    # откладываем событие
    if money_credited:
        event = ReplenishmentCompleted(
            user_id=new_replenishment.user_id,
            replenishment_id=new_replenishment.replenishment_id,
            amount=new_replenishment.amount,
            total_sum_replenishment=total_sum_replenishment,
            error=error,
            error_str=error_str,
            language=language,
            username=username
        )
        await on_replenishment_completed(event)
    else:
        event = ReplenishmentFailed(
            user_id=new_replenishment.user_id,
            replenishment_id=new_replenishment.replenishment_id,
            error_str=error_str,
            language=language,
            username=username
        )
        await on_replenishment_failed(event)


async def on_replenishment_completed(event: ReplenishmentCompleted):
    """Обрабатывается когда пользователь получил деньги и не возникло ошибки"""

    # отсылка успеха
    message_success = n_get_text(
        event.language,
        "replenishment",
        "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
        "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
        event.amount
    ).format(sum=event.amount)

    await send_message(event.user_id, message_success)

    if not event.error:
        message_log = n_get_text(
            get_config().app.default_lang,
            "replenishment",
            "#Replenishment \n\nUser {username} successfully topped up the balance by {sum} ruble. \n"
            "Replenishment ID: {replenishment_id} \n\n"
            "Time: {time}",
            "#Replenishment \n\nUser {username} successfully topped up the balance by {sum} rubles. \n"
            "Replenishment ID: {replenishment_id} \n\n"
            "Time: {time}",
            event.amount
        ).format(
            username=event.username,
            sum=event.amount,
            replenishment_id=event.replenishment_id,
            time=datetime.now().strftime(get_config().different.dt_format)
        )
        log_lvl = LogLevel.INFO
    else:
        message_log = get_text(
            get_config().app.default_lang,
            'replenishment',
            "#Replenishment_error \n\nUser {username} Paid money, balance updated, but an error occurred inside the server. \n"
            "Replenishment ID: {replenishment_id}.\nError: {error} \n\nTime: {time}"
        ).format(
            username=event.username,
            replenishment_id=event.replenishment_id,
            error=str(event.error_str),
            time=datetime.now().strftime(get_config().different.dt_format)
        )
        log_lvl = LogLevel.ERROR

    event = EventSentLog(
        text=message_log,
        log_lvl=log_lvl
    )
    await publish_event(event.model_dump(), "message.send_log")


async def on_replenishment_failed(event: ReplenishmentFailed):
    """Обрабатывается когда пользователь НЕ получил деньги"""

    message_for_user = get_text(
        event.language,
        "replenishment",
        "An error occurred while replenishing!\nReplenishment ID: {replenishment_id} "
        "\n\nWe apologize for the inconvenience. \nPlease contact support."
    ).format(replenishment_id=event.replenishment_id)

    await send_message(event.user_id, message_for_user, reply_markup=await support_kb(event.language))

    message_log = get_text(
        get_config().app.default_lang,
        "replenishment",
        "#Replenishment_error \n\nUser {username} Paid money, but the balance was not updated. \n"
        "Replenishment ID: {replenishment_id}. \nError: {error} \n\nTime: {time}"
    ).format(
        username=event.username,
        replenishment_id=event.replenishment_id,
        error=str(event.error_str),
        time=datetime.now().strftime(get_config().different.dt_format)
    )

    event = EventSentLog(
        text=message_log,
        log_lvl=LogLevel.ERROR
    )
    await publish_event(event.model_dump(), "message.send_log")
