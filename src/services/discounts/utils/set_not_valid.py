import asyncio

from datetime import datetime, timezone
from sqlalchemy import select, and_, update

from src.services.database.database import get_db
from src.services.discounts.actions.actions_vouchers import deactivate_voucher
from src.services.discounts.models import Vouchers, PromoCodes
from src.services.discounts.utils.sending import send_set_not_valid_voucher
from src.services.users.actions import get_user
from src.utils.core_logger import logger
from src.utils.i18n import get_i18n
from src.bot_actions.send_messages import send_log


async def _set_not_valid_promo_code() -> None:
    """Сделает все записи в БД is_valid=False у переданной модели если срок годности истёк"""
    async with get_db() as session:
        now = datetime.now(timezone.utc)
        result_db = await session.execute(
            update(PromoCodes)
            .where(
                and_(
                    PromoCodes.is_valid.is_(True),
                    PromoCodes.expire_at.isnot(None),
                    PromoCodes.expire_at <= now
                )
            )
            .values(is_valid=False)
            .returning(PromoCodes)
        )
        await session.commit()

        changed_promo_codes = result_db.scalars().all()
        i18n = get_i18n('ru', "discount_dom")
        for promo in changed_promo_codes:
            message_log = i18n.gettext(
                "#Promo_code_expired \nID '{id}' \nCode '{code}'"
                "\n\nThe promo code has expired due to reaching the number of activations or time limit. It is no longer possible to activate it"
            ).format(id=promo.promo_code_id, code=promo.activation_code)
            await send_log(message_log)


async def _set_not_valid_vouchers() -> None:
    async with get_db() as session_db:
        now = datetime.now(timezone.utc)
        result_db = await session_db.execute(
            select(Vouchers)
            .where(
                and_(
                    Vouchers.is_valid.is_(True),
                    Vouchers.expire_at.isnot(None),
                    Vouchers.expire_at <= now
                )
            )
        )
        vouchers = result_db.scalars().all()

        for voucher in vouchers:
            await deactivate_voucher(voucher.voucher_id)
            user = await get_user(voucher.creator_id)
            await send_set_not_valid_voucher(voucher.creator_id, voucher, False, user.language)

async def deactivate_expired_promo_codes_and_vouchers(interval: int = 60):
    """Бесконечный цикл, удаляет промокоды и ваучеры с истёкшим сроком годности"""
    while True:
        try:
            await _set_not_valid_promo_code()
            await _set_not_valid_vouchers()
        except Exception as e:
            logger.error(f"Ошибка при деактивации промокодов/ваучеров. Ошибка: {str(e)}")
        await asyncio.sleep(interval)