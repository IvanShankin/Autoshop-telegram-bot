from datetime import datetime
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import update, select

from src.broker.producer import publish_event
from src.config import DT_FORMAT
from src.services.users.actions import update_user, get_user
from src.services.users.models import WalletTransaction, UserAuditLogs, Replenishments
from src.services.database.database import get_db
from src.services.replenishments_event.schemas import NewReplenishment
from src.utils.i18n import get_i18n
from src.bot_actions.bot_instance import get_bot_logger
from src.modules.keyboard_main import support_kb
from src.services.replenishments_event.schemas import ReplenishmentCompleted, ReplenishmentFailed
from src.utils.core_logger import logger
from src.bot_actions.actions import send_log


async def replenishment_event_handler(event):
    payload = event["payload"]

    if event["event"] == "replenishment.new_replenishment":
        obj = NewReplenishment.model_validate(payload)
        await handler_new_replenishment(obj)
    if event["event"] == "replenishment.completed":
        obj = ReplenishmentCompleted.model_validate(payload)
        await on_replenishment_completed(obj)
    if event["event"] == "replenishment.failed":
        obj = ReplenishmentFailed.model_validate(payload)
        await on_replenishment_failed(obj)

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
        username = user.username
        total_sum_replenishment = user.total_sum_replenishment

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

        error = False
    except Exception as e:
        logger.error(
            f"#Ошибка_пополнения Произошла ошибка при пополнении 'handler_new_replenishment'. "
            f"Флаг обновлённого баланса: {money_credited}. "
            f"ID пополнения: {new_replenishment.replenishment_id}. "
            f"Ошибка: {str(e)}"
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
            logger.error(f"Не удалось обновить данные о новом пополнении. Ошибка: {str(e)}")
            await send_log(f"Не удалось обновить данные о новом пополнении. \nОшибка: {str(e)}")

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
        await publish_event(event.model_dump(), 'replenishment.completed')  # публикация события
    else:
        event = ReplenishmentFailed(
            user_id=new_replenishment.user_id,
            replenishment_id=new_replenishment.replenishment_id,
            error_str=error_str,
            language=language,
            username=username
        )
        await publish_event(event.model_dump(), 'replenishment.failed')  # публикация события

async def on_replenishment_completed(event: ReplenishmentCompleted):
    """Обрабатывается когда пользователь получил деньги и не возникло ошибки"""
    i18n = get_i18n(event.language, "replenishment_dom")

    # отсылка успеха
    message_success = i18n.ngettext(
        "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
        "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
        event.amount
    ).format(sum=event.amount)

    try:
        bot = await get_bot_logger()
        await bot.send_message(event.user_id, message_success)
    except TelegramForbiddenError:  # если бот заблокирован у пользователя
        pass

    if not event.error:
        message_log = i18n.ngettext(
            "#Replenishment \n\nUser @{username} successfully topped up the balance by {sum} ruble. \n"
            "Replenishment ID: {replenishment_id} \n\n"
            "Time: {time}",
            "#Replenishment \n\nUser @{username} successfully topped up the balance by {sum} rubles. \n"
            "Replenishment ID: {replenishment_id}  \n\n"
            "Time: {time}",
            event.amount
        ).format(
            username=event.username,
            sum=event.amount,
            replenishment_id=event.replenishment_id,
            time=datetime.now().strftime(DT_FORMAT)
        )
    else:
        message_log = i18n.gettext(
            "#Replenishment_error \n\nUser @{username} Paid money, balance updated, but an error occurred inside the server. \n"
            "Replenishment ID: {replenishment_id}.\nError: {error} \n\nTime: {time}"
        ).format(
            username=event.username,
            replenishment_id=event.replenishment_id,
            error=str(event.error_str),
            time=datetime.now().strftime(DT_FORMAT)
        )

    await send_log(message_log)

async def on_replenishment_failed(event: ReplenishmentFailed):
    """Обрабатывается когда пользователь НЕ получил деньги"""
    i18n = get_i18n(event.language, "replenishment_dom")

    message_for_user = i18n.gettext(
        "An error occurred while replenishing!\nReplenishment ID: {replenishment_id} "
        "\n\nWe apologize for the inconvenience. \nPlease contact support."
    ).format(replenishment_id=event.replenishment_id)

    try:
        bot = await get_bot_logger()
        await bot.send_message(event.user_id, message_for_user, reply_markup=await support_kb(event.language))
    except TelegramForbiddenError:  # если бот заблокирован у пользователя
        pass

    message_log = i18n.gettext(
        "#Replenishment_error \n\nUser @{username} Paid money, but the balance was not updated. \n"
        "Replenishment ID: {replenishment_id}. \nError: {error} \n\nTime: {time}"
    ).format(
        username=event.username,
        replenishment_id=event.replenishment_id,
        error=str(event.error_str),
        time=datetime.now().strftime(DT_FORMAT)
    )

    await send_log(message_log)
