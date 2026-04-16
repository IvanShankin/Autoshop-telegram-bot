import json
from logging import Logger

from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.users import ReplenishmentsService
from src.application.payments.crypto_bot.schemas import WebhookCryptoBotDTO
from src.models.read_models import NewReplenishment
from src.models.read_models.other import ReplenishmentsDTO
from src.models.update_models.users import UpdateReplenishment


class ProcessCryptoWebhookUseCase:

    def __init__(
        self,
        replenishment_service: ReplenishmentsService,
        publish_event_handler: PublishEventHandler,
        logger: Logger,
    ):
        self.replenishment_service = replenishment_service
        self.publish_event_handler = publish_event_handler
        self.logger = logger

    async def execute(self, webhook: WebhookCryptoBotDTO):
        if webhook.update_type != "invoice_paid":
            return

        payload = webhook.payload.payload

        if not payload:
            self.logger.warning("[ProcessCryptoWebhookUseCase] получили пустой payload")
            return

        data_in_dict: dict = json.loads(payload)
        replenishment = ReplenishmentsDTO(**data_in_dict)

        await self.replenishment_service.update_replenishment(
            replenishment_id=replenishment.replenishment_id,
            data=UpdateReplenishment(
                status="processing"
            ),
            make_commit=True,
        )

        await self.publish_event_handler.new_replenishment(
            data=NewReplenishment(
                replenishment_id=replenishment.replenishment_id,
                user_id=replenishment.user_id,
                origin_amount=replenishment.origin_amount,
                amount=replenishment.amount,
            ),
        )