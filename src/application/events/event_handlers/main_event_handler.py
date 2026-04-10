from logging import Logger
from typing import Callable, Awaitable, Any

from src.application.events.event_handlers.file_system import FileSystemEventHandler
from src.application.events.event_handlers.message import MessageEventHandler
from src.application.events.event_handlers.promo_code import PromoCodeEventHandler
from src.application.events.event_handlers.purchase import PurchaseEventHandler
from src.application.events.event_handlers.referrals import ReferralEventHandler
from src.application.events.event_handlers.replenishments import ReplenishmentsEventHandler


class EventHandler:
    """Установить в consumer при запуске приложения"""

    def __init__(
        self,
        promo_code_ev_hand: PromoCodeEventHandler,
        referral_ev_hand: ReferralEventHandler,
        replenishment_ev_hand: ReplenishmentsEventHandler,
        purchase_ev_hand: PurchaseEventHandler,
        filesystem_ev_hand: FileSystemEventHandler,
        message_ev_hand: MessageEventHandler,
        logger: Logger,
    ):
        self.logger = logger
        self._handlers: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {
            "promo_code": promo_code_ev_hand.promo_code_event_handler,
            "referral": referral_ev_hand.referral_event_handler,
            "replenishment": replenishment_ev_hand.replenishment_event_handler,
            "purchase": purchase_ev_hand.purchase_event_handler,
            "_filesystem": filesystem_ev_hand.filesystem_event_handler,
            "message": message_ev_hand.message_event_handler,
        }

    async def handle(self, body: dict[str, Any]) -> None:
        event_type = body.get("event")

        if not event_type:
            self.logger.warning(f"[EventHandler]. Event not found. Body: {body}")
            return

        prefix = event_type.split(".")[0]

        handler = self._handlers.get(prefix)

        if not handler:
            self.logger.warning(f"[EventHandler]. Handler not found. event_type: {event_type}")
            return

        await handler(body)
