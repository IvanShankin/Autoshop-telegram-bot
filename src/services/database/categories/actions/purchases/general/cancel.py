import asyncio
import os
import shutil
from logging import Logger
from typing import List, Tuple

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.database.categories.models import PurchaseRequests
from src.services.database.users.models.models_users import BalanceHolder


async def update_purchaseRequests_and_balance_holder(session: AsyncSession, logger: Logger, purchase_request_id: int):
    """
    :param session: сессия БД в транзакции
    """
    try:
        await session.execute(
            update(PurchaseRequests)
            .where(PurchaseRequests.purchase_request_id == purchase_request_id)
            .values(status='failed')
        )
        await session.execute(
            update(BalanceHolder)
            .where(BalanceHolder.purchase_request_id == purchase_request_id)
            .values(status='released')
        )
    except Exception:
        logger.exception("Failed to update purchase request / balance holder status")


async def return_files(
    mapping: List[Tuple[str, str, str]],
    logger: Logger,
):
    """
    :param mapping: List(orig_path, temp_path, final_path)
    :return:
    """
    # Попытаться вернуть временные файлы обратно (temp -> orig) если они существуют
    for orig, temp, final in mapping:
        for src in (temp, final):
            if src and os.path.exists(src):
                try:
                    os.makedirs(os.path.dirname(orig), exist_ok=True)
                    await asyncio.to_thread(shutil.move, src, orig)
                    break
                except Exception:
                    logger.exception("Failed to restore file for %s from %s", orig, src)

        # если final уже существует (переименование успело произойти), попытаться вернуть final -> orig
        try:
            if final and os.path.exists(final):
                await asyncio.to_thread(shutil.move, final, orig)
        except Exception:
            logger.exception("Failed to move final back to orig for %s", orig)

