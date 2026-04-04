from sqlalchemy.ext.asyncio import AsyncSession

from src.models.read_models import LogLevel
from src.exceptions.business import AlreadyActivated
from src.exceptions.domain import PromoCodeNotFound
from src.config import get_config
from src.services._database.discounts.events.schemas import NewActivatePromoCode
from src.services.events.publish_event_handler import PublishEventHandler
from src.services.models.discounts import PromoCodeService
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text


class PromoCodeEventHandler:

    def __init__(
        self,
        publish_event: PublishEventHandler,
        promo_code_service: PromoCodeService,
        session_db: AsyncSession,
    ):
        self.publish_event = publish_event
        self.promo_code_service = promo_code_service
        self.session_db = session_db

    async def promo_code_event_handler(self, event):
        payload = event["payload"]

        if event["event"] == "promo_code.activated":
            obj = NewActivatePromoCode.model_validate(payload)
            await self._handler_new_activate_promo_code(obj)

    async def _handler_new_activate_promo_code(self, new_activate: NewActivatePromoCode):
        """Необходимо вызывать когда совершена покупка."""
        try:
            result_activate = await self.promo_code_service.activate_promo_code(
                new_activate.promo_code_id, user_id=new_activate.user_id
            )

            await self._on_new_activate_promo_code_completed(
                result_activate.promo_code.promo_code_id,
                new_activate.user_id,
                result_activate.promo_code.activation_code,
                result_activate.promo_code.number_of_activations - result_activate.promo_code.activated_counter
            )

            if result_activate.deactivate:
                await self._send_promo_code_expired(
                    new_activate.promo_code_id, result_activate.promo_code.activation_code
                )

        except (PromoCodeNotFound, AlreadyActivated):
            return
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"Произошла ошибка, записи об активации промокода. Ошибка: {str(e)}")
            await self._on_new_activate_promo_code_failed(new_activate.promo_code_id, str(e))

    async def _on_new_activate_promo_code_completed(self, promo_code_id: int, user_id: int, activation_code: str, activations_left: int):
        await self.publish_event.send_log(
            text=get_text(
                get_config().app.default_lang,
                "discount",
                "log_promo_code_activation"
            ).format(promo_code_id=promo_code_id, code=activation_code, user_id=user_id,
                     number_of_activations=activations_left),
            log_lvl=LogLevel.INFO
        )

    async def _send_promo_code_expired(self, promo_code_id: int, activation_code: str):
        await self.publish_event.send_log(
            text=get_text(
                get_config().app.default_lang,
                "discount",
                "log_promo_code_expired"
            ).format(id=promo_code_id, code=activation_code),
            log_lvl=LogLevel.INFO
        )

    async def _on_new_activate_promo_code_failed(self, promo_code_id: int, error: str):
        await self.publish_event.send_log(
            text=get_text(
                get_config().app.default_lang,
                "discount",
                "log_error_activating_promo_code"
            ).format(id=promo_code_id, error=error),
            log_lvl=LogLevel.INFO
        )


