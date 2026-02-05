from datetime import datetime, timezone

from sqlalchemy import update, select

from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.broker.producer import publish_event
from src.config import get_config
from src.services.redis.core_redis import get_redis
from src.services.database.discounts.events.schemas import NewActivatePromoCode
from src.services.database.discounts.models import PromoCodes, ActivatedPromoCodes
from src.services.database.core.database import get_db
from src.services.database.users.models import UserAuditLogs
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text
from src.bot_actions.messages import send_log


async def promo_code_event_handler(event):
    payload = event["payload"]

    if event["event"] == "promo_code.activated":
        obj = NewActivatePromoCode.model_validate(payload)
        await handler_new_activate_promo_code(obj)

async def handler_new_activate_promo_code(new_activate: NewActivatePromoCode):
    """Необходимо вызывать когда совершена покупка."""
    promo_code_deactivated = False
    try:
        async with get_db() as session_db:
            result_db = await session_db.execute(select(PromoCodes).where(PromoCodes.promo_code_id == new_activate.promo_code_id))
            promo_code = result_db.scalar_one_or_none()
            if not promo_code: # если промокод не найден
                return

            # проверка на повторную активацию
            result_db = await session_db.execute(
                select(ActivatedPromoCodes)
                .where(
                    (ActivatedPromoCodes.promo_code_id == new_activate.promo_code_id) &
                    (ActivatedPromoCodes.user_id == new_activate.user_id)
                )
            )
            activate_promo_code = result_db.scalar_one_or_none()
            if activate_promo_code: # если активировал ранее 
                return

            # активация промокода
            result_db = await session_db.execute(
                update(PromoCodes)
                .where(PromoCodes.promo_code_id == new_activate.promo_code_id)
                .values(activated_counter = promo_code.activated_counter + 1)
                .returning(PromoCodes.activated_counter)
            )
            new_activated_counter = result_db.scalar_one()

            new_activate_promo = ActivatedPromoCodes(
                promo_code_id=new_activate.promo_code_id,
                user_id=new_activate.user_id
            )
            session_db.add(new_activate_promo)
            await session_db.commit()
            await session_db.refresh(new_activate_promo)

            if (new_activated_counter >= promo_code.number_of_activations) or (datetime.now(timezone.utc) > promo_code.expire_at):
                await session_db.execute(
                    update(PromoCodes)
                    .where(PromoCodes.promo_code_id == new_activate.promo_code_id)
                    .values(is_valid = False)
                )
                await session_db.commit()

                async with get_redis() as session_redis:
                    await session_redis.delete(f'promo_code:{promo_code.activation_code}')

                promo_code_deactivated = True

            await on_new_activate_promo_code_completed(
                promo_code.promo_code_id,
                new_activate.user_id,
                promo_code.activation_code,
                promo_code.number_of_activations - new_activated_counter
            )

            if promo_code_deactivated:
                await send_promo_code_expired(promo_code.promo_code_id, promo_code.activation_code)

            new_user_log= UserAuditLogs(
                user_id=new_activate.user_id,
                action_type="new_activate_promo_code",
                message='Пользователь активировал промокод',
                details={
                    "promo_code_id": new_activate.promo_code_id,
                },
            )
            session_db.add(new_user_log)
            await session_db.commit()

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Произошла ошибка, записи об активации промокода. Ошибка: {str(e)}")
        await on_new_activate_promo_code_failed(new_activate.promo_code_id, str(e))


async def on_new_activate_promo_code_completed(promo_code_id: int, user_id: int, activation_code: str, activations_left: int):
    event = EventSentLog(
        text=get_text(
            get_config().app.default_lang,
            "discount",
            "#Promocode_activation \nID promo_code '{promo_code_id}' \nCode '{code}' \nID user '{user_id}'"
            "\n\nSuccessfully activated. \nActivations remaining: {number_of_activations}"
        ).format(promo_code_id=promo_code_id, code=activation_code, user_id=user_id, number_of_activations=activations_left),
        log_lvl=LogLevel.INFO
    )
    await publish_event(event.model_dump(), "message.send_log")

async def send_promo_code_expired(promo_code_id: int, activation_code: str):
    event = EventSentLog(
        text=get_text(
            get_config().app.default_lang,
            "discount",
            "#Promo_code_expired \nID '{id}' \nCode '{code}'"
            "\n\nThe promo code has expired due to reaching the number of activations or time limit. It is no longer possible to activate it"
        ).format(id=promo_code_id, code=activation_code),
        log_lvl=LogLevel.INFO
    )
    await publish_event(event.model_dump(), "message.send_log")

async def on_new_activate_promo_code_failed(promo_code_id: int, error: str):
    event = EventSentLog(
        text=get_text(
            get_config().app.default_lang,
            "discount",
            "#Error_activating_promo_code \n\nPromo code ID '{id}' \nError: {error}"
        ).format(id=promo_code_id, error=error),
        log_lvl=LogLevel.INFO
    )
    await publish_event(event.model_dump(), "message.send_log")


