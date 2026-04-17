from datetime import datetime

from src.config import Config
from src.models.read_models import LogLevel
from src.exceptions.telegram import TelegramForbiddenErrorService
from src.models.read_models import ReferralIncomeResult, ReferralReplenishmentCompleted
from src.application.bot import SendMessageService
from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.referrals import ReferralService
from src.application.models.users.notifications_service import NotificationSettingsService
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text


class ReferralEventHandler:

    def __init__(
        self,
        publish_event: PublishEventHandler,
        referral_service: ReferralService,
        notification_service: NotificationSettingsService,
        send_msg_service: SendMessageService,
        conf: Config,
    ):
        self.publish_event = publish_event
        self.referral_service = referral_service
        self.notification_service = notification_service
        self.send_msg_service = send_msg_service
        self.conf = conf

    async def referral_event_handler(self, event):
        payload = event["payload"]

        if event["event"] == "referral.new_referral":
            obj = ReferralReplenishmentCompleted.model_validate(payload)
            await self._handler_referral_replenishment(obj)

    async def _handler_referral_replenishment(
        self,
        data: ReferralReplenishmentCompleted,
    ):
        try:
            result = await self.referral_service.process_referral_replenishment(data)
            if not result:
                return

            notifications = await self.notification_service.get_notification(result.owner_user_id)
            if notifications and notifications.referral_replenishment:
                await self._notify_owner_on_income(result)
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(
                "Ошибка при начислении дохода владельцу реферала. "
                "replenishment_id=%s, error=%s",
                data.replenishment_id,
                str(e),
            )
            await self._on_referral_income_failed(str(e))

    async def _notify_owner_on_income(self, result: ReferralIncomeResult) -> None:
        try:
            message = self._build_referral_income_message(result)
            await self.send_msg_service.send(result.owner_user_id, message)
        except TelegramForbiddenErrorService:
            return
        except Exception as e:
            logger = get_logger(__name__)
            logger.exception(
                "Ошибка при отправке сообщения о пополнении от реферала. "
                "owner_id=%s, error=%s",
                result.owner_user_id,
                str(e),
            )
            await self._on_referral_income_failed(str(e))

    def _build_referral_income_message(self, result: ReferralIncomeResult) -> str:
        if result.last_level == result.current_level:
            message = get_text(
                result.owner_language,
                "referral_messages",
                "referral_replenished_balance",
            ).format(
                level=result.current_level,
                amount=result.replenishment_amount,
                percent=result.percent,
            )
        else:
            message = get_text(
                result.owner_language,
                "referral_messages",
                "referral_replenished_and_level_up",
            ).format(
                last_lvl=result.last_level,
                current_lvl=result.current_level,
                amount=result.replenishment_amount,
                percent=result.percent,
            )
        return message

    async def _on_referral_income_failed(self, error: str) -> None:
        await self.publish_event.send_log(
            text=get_text(
                self.conf.app.default_lang,
                "referral_messages",
                "log_replenishment_error",
            ).format(
                error=error,
                time=datetime.now().strftime(self.conf.different.dt_format),
            ),
            log_lvl=LogLevel.ERROR,
        )
