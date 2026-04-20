from typing import TYPE_CHECKING

from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.users import UserService
from src.infrastructure.translations import get_text
from src.models.read_models import NewActivationVoucher, LogLevel


if TYPE_CHECKING:
    from src.infrastructure.telegram.bot_client import TelegramClient


class VoucherEventHandler:

    def __init__(
        self,
        publish_event_handler: PublishEventHandler,
        user_service: UserService,
        tg_client: "TelegramClient",
    ):
        self.publish_event_handler = publish_event_handler
        self.user_service = user_service
        self.tg_client = tg_client


    async def voucher_event_handler(self, event):
        payload = event["payload"]

        if event["event"] == "voucher.activated":
            obj = NewActivationVoucher.model_validate(payload)
            await self.handler_new_activated_voucher(obj)

    async def handler_new_activated_voucher(self, new_activation_voucher: NewActivationVoucher):
        """Отошлёт владельцу сообщение об активации и если ваучер стал невалидным `is_valid == False`, то сообщит, что он закончился"""
        voucher = new_activation_voucher.voucher
        if voucher.is_created_admin:
            await self.publish_event_handler.send_log(
                text=f"#Активация_ваучера \n\nID: {voucher.voucher_id}\nCode: {voucher.activation_code}\n"
                     f"Осталось активаций: {voucher.number_of_activations - voucher.activated_counter if voucher.number_of_activations else "бесконечно..."}",
                log_lvl=LogLevel.INFO,
            )
            if not new_activation_voucher.voucher.is_valid:
                if voucher.is_created_admin:
                    await self.publish_event_handler.send_log(
                        text=f"#Деактивация_ваучера_созданным_админом (автоматически)\n\nID: {voucher.voucher_id}",
                        log_lvl=LogLevel.INFO,
                    )
        else:
            owner = await self.user_service.get_user(voucher.creator_id)
            message_for_user = get_text(
                owner.language,
                "discount",
                "log_voucher_activated"
            ).format(code=voucher.activation_code, number_activations=voucher.number_of_activations - voucher.activated_counter)
            await self.tg_client.send_message(owner.user_id, message_for_user)

            if not new_activation_voucher.voucher.is_valid:
                message_for_user = get_text(
                    owner.language,
                    "discount",
                    "voucher_reached_activation_limit"
                ).format(
                    id=voucher.voucher_id,
                    code=voucher.activation_code,
                )
                await self.tg_client.send_message(owner.user_id, message_for_user)