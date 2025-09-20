from sqlalchemy import update, select

from src.redis_dependencies.core_redis import get_redis
from src.services.database.database import get_db
from src.services.discounts.utils.sending import send_set_not_valid_voucher
from src.services.discounts.events.schemas import NewActivationVoucher
from src.services.discounts.models import Vouchers, VoucherActivations
from src.services.users.models import UserAuditLogs, WalletTransaction
from src.utils.i18n import get_i18n
from src.utils.send_messages import send_log


async def voucher_event_handler(event):
    payload = event["payload"]

    if event["event"] == "voucher.activated":
        obj = NewActivationVoucher.model_validate(payload)
        await handler_new_activated_voucher(obj)

async def handler_new_activated_voucher(new_activation_voucher: NewActivationVoucher):
    """Обрабатывает новую активацию ваучера"""
    try:
        async with get_db() as session_db:
            # проверка на повторную активацию
            result_db = await session_db.execute(
                select(VoucherActivations)
                .where(VoucherActivations.vouchers_id == new_activation_voucher.voucher_id)
            )
            activated_voucher= result_db.scalar_one_or_none()
            if activated_voucher:  # если активировал ранее
                return

            result_db = await session_db.execute(
                update(Vouchers)
                .where(Vouchers.voucher_id == new_activation_voucher.voucher_id)
                .values(activated_counter = Vouchers.activated_counter + 1 )
                .returning(Vouchers)
            )
            voucher = result_db.scalar_one_or_none()
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
                    new_activation_voucher.user_id,
                    voucher,
                    True,
                    new_activation_voucher.language
                )

            new_activated = VoucherActivations(
                vouchers_id=new_activation_voucher.voucher_id,
                user_id=new_activation_voucher.user_id,
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
                details= {
                    "message": "Ваучер активирован",
                    "voucher_id": voucher.voucher_id,
                    "amount": new_activation_voucher.amount
                }
            )

            session_db.add(new_activated)
            session_db.add(new_wallet_transaction)
            session_db.add(new_user_log)

            await session_db.commit()
    except Exception as e:
        await send_failed(new_activation_voucher.voucher_id, str(e))


async def send_failed(voucher_id: int, error: str):
    i18n = get_i18n('ru', "replenishment_dom")
    message_log = i18n.gettext(
        "Error_while_activating_voucher. \n\nVoucher ID '{id}' \nError: {error}"
    ).format(id=voucher_id, error=error)
    await send_log(message_log)

