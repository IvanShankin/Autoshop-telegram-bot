import asyncio
from datetime import datetime, timezone

from sqlalchemy import update, and_

from src.services.database.core import get_db
from src.services.database.users.models import Replenishments, UserAuditLogs
from src.utils.core_logger import logger


async def _set_cancelled_replenishment():
    async with get_db() as session_db:
        now = datetime.now(timezone.utc)
        result_db = await session_db.execute(
            update(Replenishments)
            .where(
                and_(
                    Replenishments.status.is_('pending'),
                    Replenishments.expire_at <= now
                )
            )
        )
        replenishments: list[Replenishments] = result_db.scalars().all()

        for rep in replenishments:
            log = UserAuditLogs(
                user_id=rep.user_id,
                action_type="deactivate_replenishment",
                message='Счёт для пополнения автоматически отменён из-за истечения его срока годности',
                details={
                    "amount": rep.amount,
                    "replenishments_id": rep.replenishment_id,
                },
            )
            session_db.add(log)

        await session_db.commit()


async def deactivate_expired_replenishments(interval: int = 60):
    """Бесконечный цикл, удаляет промокоды и ваучеры с истёкшим сроком годности"""
    while True:
        try:
            await _set_cancelled_replenishment()
        except Exception as e:
            logger.error(f"Ошибка при попытки установить 'cancelled' пополнение. Ошибка: {str(e)}")
        await asyncio.sleep(interval)