from src.infrastructure.rabbit_mq.producer import RabbitMQProducer
from src.models.read_models.events.discounts import NewActivationVoucher, NewActivatePromoCode
from src.models.read_models import EventSentLog, LogLevel, NewPurchaseAccount, NewPurchaseUniversal, NewReplenishment
from src.models.read_models import EventCreateUiImage


class PublishEventHandler:

    def __init__(
        self,
        producer: RabbitMQProducer,
    ):
        self.producer = producer

    async def send_log(self, text: str, log_lvl: LogLevel = None):
        event = EventSentLog(text=text, log_lvl=log_lvl)
        await self.producer.publish(event.model_dump(), "message.send_log")

    async def create_ui_image(
        self,
        ui_image_key: str,
    ):
        await self.producer.publish(
            EventCreateUiImage(ui_image_key=ui_image_key).model_dump(),
            "filesystem.create_ui_image"
        )

    async def promo_code_activated(
        self,
        promo_code_id: int,
        user_id: int,
    ):
        new_activate = NewActivatePromoCode(
            promo_code_id=promo_code_id,
            user_id=user_id,
        )
        await self.producer.publish(new_activate.model_dump(), "promo_code.activated")

    async def voucher_activated(self, data: NewActivationVoucher):
        await self.producer.publish(data.model_dump(), "voucher.activated")

    async def new_purchase_account(self, data: NewPurchaseAccount):
        await self.producer.publish(data.model_dump(), "purchase.account")

    async def new_purchase_universal(self, data: NewPurchaseUniversal):
        await self.producer.publish(data.model_dump(), "purchase.universal")

    async def new_replenishment(self, data: NewReplenishment):
        await self.producer.publish(data.model_dump(), "replenishment.new_replenishment")