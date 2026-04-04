from datetime import datetime

from src.models.read_models import LogLevel
from src.config import get_config
from src.models.read_models import NewReplenishment, ReplenishmentCompleted, ReplenishmentFailed
from src.services.bot import SendMessageService
from src.services.events.publish_event_handler import PublishEventHandler
from src.services.models.users.replenishment_service import ReplenishmentsService
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text, n_get_text
from src.modules.keyboard_main import support_kb


class ReplenishmentsEventHandler:

    def __init__(
        self,
        publish_event: PublishEventHandler,
        replenishment_service: ReplenishmentsService,
        send_msg_service: SendMessageService,
    ):
        self.publish_event = publish_event
        self.replenishment_service = replenishment_service
        self.send_msg_service = send_msg_service

    async def replenishment_event_handler(self, event):
        payload = event["payload"]

        if event["event"] == "replenishment.new_replenishment":
            obj = NewReplenishment.model_validate(payload)
            await self._handle_new_replenishment(obj)

    async def _handle_new_replenishment(self, new_replenishment: NewReplenishment):
        try:
            result = await self.replenishment_service.process_new_replenishment(new_replenishment)
            if not result:
                return

            if isinstance(result, ReplenishmentCompleted):
                await self._on_replenishment_completed(result)
            elif isinstance(result, ReplenishmentFailed):
                await self._on_replenishment_failed(result)
        except Exception as e:
            logger = get_logger(__name__)
            logger.exception(
                "Ошибка при обработке пополнения. replenishment_id=%s, error=%s",
                new_replenishment.replenishment_id,
                str(e),
            )
            await self._send_error_log(str(e))

    async def _on_replenishment_completed(self, event: ReplenishmentCompleted):
        message_success = n_get_text(
            event.language,
            "replenishment",
            "balance_successfully_replenished",
            "balance_successfully_replenished",
            event.amount,
        ).format(sum=event.amount)

        await self.send_msg_service.send(event.user_id, message_success)

        if not event.error:
            message_log = n_get_text(
                get_config().app.default_lang,
                "replenishment",
                "log_replenishment",
                "log_replenishment",
                event.amount,
            ).format(
                username=self._format_username(event),
                sum=event.amount,
                replenishment_id=event.replenishment_id,
                time=datetime.now().strftime(get_config().different.dt_format),
            )
            log_lvl = LogLevel.INFO
        else:
            message_log = get_text(
                get_config().app.default_lang,
                "replenishment",
                "log_replenishment_error_server",
            ).format(
                username=self._format_username(event),
                replenishment_id=event.replenishment_id,
                error=str(event.error_str),
                time=datetime.now().strftime(get_config().different.dt_format),
            )
            log_lvl = LogLevel.ERROR

        await self.publish_event.send_log(text=message_log, log_lvl=log_lvl)

    async def _on_replenishment_failed(self, event: ReplenishmentFailed):
        message_for_user = get_text(
            event.language,
            "replenishment",
            "error_while_replenishing",
        ).format(replenishment_id=event.replenishment_id)

        await self.send_msg_service.send(
            event.user_id,
            message_for_user,
            reply_markup=await support_kb(event.language),
        )

        message_log = get_text(
            get_config().app.default_lang,
            "replenishment",
            "log_replenishment_error_balance_not_updated",
        ).format(
            username=self._format_username(event),
            replenishment_id=event.replenishment_id,
            error=str(event.error_str),
            time=datetime.now().strftime(get_config().different.dt_format),
        )

        await self.publish_event.send_log(text=message_log, log_lvl=LogLevel.ERROR)

    def _format_username(self, event: ReplenishmentCompleted | ReplenishmentFailed) -> str:
        if event.username:
            return f"@{event.username}"
        return get_text(event.language, "miscellaneous", "no")

    async def _send_error_log(self, error: str) -> None:
        await self.publish_event.send_log(
            text=get_text(
                get_config().app.default_lang,
                "replenishment",
                "log_replenishment_error_balance_not_updated",
            ).format(
                username=get_text(get_config().app.default_lang, "miscellaneous", "no"),
                replenishment_id="unknown",
                error=error,
                time=datetime.now().strftime(get_config().different.dt_format),
            ),
            log_lvl=LogLevel.ERROR,
        )
