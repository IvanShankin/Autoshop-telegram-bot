from sqlalchemy import update

from src.bot_actions.messages.schemas import LogLevel, EventSentLog
from src.broker.producer import publish_event
from src.config import get_config
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db
from src.services.database.discounts.utils.sending import send_set_not_valid_voucher
from src.services.database.discounts.events.schemas import NewActivationVoucher
from src.services.database.discounts.models import Vouchers
from src.services.database.users.actions import get_user
from src.services.database.users.models import UserAuditLogs, WalletTransaction
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text
from src.bot_actions.messages import send_message


async def voucher_event_handler(event):
    payload = event["payload"]

    if event["event"] == "voucher.activated":
        obj = NewActivationVoucher.model_validate(payload)
        await handler_new_activated_voucher(obj)

async def handler_new_activated_voucher(new_activation_voucher: NewActivationVoucher):
    """Залогирует все действия и отошлёт владельцу сообщение об активации"""
    try:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                update(Vouchers)
                .where(Vouchers.voucher_id == new_activation_voucher.voucher_id)
                .values(activated_counter = Vouchers.activated_counter + 1 )
                .returning(Vouchers)
            )
            voucher: Vouchers = result_db.scalar_one_or_none()
            await session_db.commit()

            set_not_valid = False
            if voucher.number_of_activations and (voucher.activated_counter >= voucher.number_of_activations):
                set_not_valid = True

            if set_not_valid: # если необходимо ваучер установить невалидным
                await session_db.execute(
                    update(Vouchers)
                    .where(Vouchers.voucher_id == new_activation_voucher.voucher_id)
                    .values(is_valid=False)
                )

                async with get_redis() as session_redis:
                    await session_redis.delete(f"voucher:{voucher.activation_code}")

                await send_set_not_valid_voucher(
                    voucher.creator_id,
                    voucher,
                    True,
                    new_activation_voucher.language
                )
            new_wallet_transaction = WalletTransaction(
                user_id=new_activation_voucher.user_id,
                type='voucher',
                amount=new_activation_voucher.amount,
                balance_before=new_activation_voucher.balance_before,
                balance_after=new_activation_voucher.balance_after
            )
            new_user_log = UserAuditLogs(
                user_id=new_activation_voucher.user_id,
                action_type="activated_voucher",
                message="Ваучер активирован",
                details= {
                    "voucher_id": voucher.voucher_id,
                    "amount": new_activation_voucher.amount
                }
            )

            session_db.add(new_wallet_transaction)
            session_db.add(new_user_log)

            await session_db.commit()

            if not voucher.is_created_admin:
                owner = await get_user(voucher.creator_id)
                message_for_user = get_text(
                    owner.language,
                    "discount",
                    "log_voucher_activated"
                ).format(code=voucher.activation_code, number_activations=voucher.number_of_activations - voucher.activated_counter)

                await send_message(owner.user_id, message_for_user)

    except Exception as e:
        get_logger(__name__).exception(f"{e}")
        await send_failed(new_activation_voucher.voucher_id, str(e))


async def send_failed(voucher_id: int, error: str):
    event = EventSentLog(
        text=get_text(
            get_config().app.default_lang,
            "discount",
            "log_error_activating_voucher"
        ).format(id=voucher_id, error=error),
        log_lvl=LogLevel.ERROR
    )
    await publish_event(event.model_dump(), "message.send_log")


