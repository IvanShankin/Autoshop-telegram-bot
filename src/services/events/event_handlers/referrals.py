from datetime import datetime

from aiogram.exceptions import TelegramForbiddenError

from src.bot_actions.messages import send_message
from src.bot_actions.messages.schemas import LogLevel
from src.config import get_config
from src.models.read_models import ReferralIncomeResult, ReferralReplenishmentCompleted
from src.services.events.publish_event_handler import PublishEventHandler
from src.services.models.referrals import ReferralService
from src.services.models.users.notifications_service import NotificationSettingsService
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text


class ReferralEventHandler:

    def __init__(
        self,
        publish_event: PublishEventHandler,
        referral_service: ReferralService,
        notification_service: NotificationSettingsService,
    ):
        self.publish_event = publish_event
        self.referral_service = referral_service
        self.notification_service = notification_service

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
            await send_message(result.owner_user_id, message)
        except TelegramForbiddenError:
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
                get_config().app.default_lang,
                "referral_messages",
                "log_replenishment_error",
            ).format(
                error=error,
                time=datetime.now().strftime(get_config().different.dt_format),
            ),
            log_lvl=LogLevel.ERROR,
        )
