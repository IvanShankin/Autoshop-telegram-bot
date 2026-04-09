import asyncio
import os
import shutil
from logging import Logger
from typing import List, Tuple

from src.application.models.purchases.general.purchase_request_service import PurchaseRequestService


class PurchaseCancelService:

    def __init__(self, purchase_request_service: PurchaseRequestService):
        self.purchase_request_service = purchase_request_service

    async def mark_failed(self, purchase_request_id: int, logger: Logger) -> None:
        try:
            await self.purchase_request_service.mark_request_status(purchase_request_id, "failed")
            await self.purchase_request_service.mark_balance_holder_status(purchase_request_id, "released")
        except Exception:
            logger.exception("Failed to update purchase request / balance holder status")

    async def return_files(
        self,
        mapping: List[Tuple[str, str, str]],
        logger: Logger,
    ) -> None:
        """
        :param mapping: List(orig_path, temp_path, final_path)
        """
        for orig, temp, final in mapping:
            for src in (temp, final):
                if src and os.path.exists(src):
                    try:
                        os.makedirs(os.path.dirname(orig), exist_ok=True)
                        await asyncio.to_thread(shutil.move, src, orig)
                        break
                    except Exception:
                        logger.exception("Failed to restore file for %s from %s", orig, src)

            try:
                if final and os.path.exists(final):
                    await asyncio.to_thread(shutil.move, final, orig)
            except Exception:
                logger.exception("Failed to move final back to orig for %s", orig)
