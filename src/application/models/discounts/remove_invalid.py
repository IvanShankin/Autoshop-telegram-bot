from datetime import datetime, timezone
from logging import Logger
from typing import TYPE_CHECKING

from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.discounts import VoucherService, PromoCodeService
from src.application.models.users import UserService
from src.models.read_models import LogLevel, VouchersDTO
from src.repository.database.discount import PromoCodeRepository, VouchersRepository
from src.infrastructure.translations import get_text


if TYPE_CHECKING:
    from src.infrastructure.telegram.bot_client import TelegramClient


class RemoveInvalidDiscountsUseCase:

    def __init__(
        self,
        user_service: UserService,
        promo_code_repo: PromoCodeRepository,
        promo_code_service: PromoCodeService,
        voucher_repo: VouchersRepository,
        voucher_service: VoucherService,
        publish_event_handler: PublishEventHandler,
        tg_client: "TelegramClient",
        logger: Logger,
    ):
        self.user_service = user_service
        self.promo_code_repo = promo_code_repo
        self.promo_code_service = promo_code_service
        self.voucher_repo = voucher_repo
        self.voucher_service = voucher_service
        self.publish_event_handler = publish_event_handler
        self.tg_client = tg_client
        self.logger = logger

    async def execute(self):
        try:
            now = datetime.now(timezone.utc)

            await self._set_not_valid_promo_code(now)
            await self._set_not_valid_vouchers(now)

        except Exception as e:
            self.logger.exception(
                "Ошибка при деактивации промокодов/ваучеров: %s", e
            )

    async def _send_set_not_valid_voucher(self, user_id: int, voucher: VouchersDTO, limit_reached: bool, language: str):
        """
        Отошлёт сообщение в канал или пользователю в зависимости от 'is_created_admin' в voucher
        :param user_id: id пользователя
        :param voucher: объект БД ваучера
        :param limit_reached: флаг получения лимита по активации
        :param language: язык пользователя
        :return:
        """
        if voucher.is_created_admin: # отсылка лога в канал
            await self.publish_event_handler.send_log(
                text=get_text(
                    'ru',
                    "discount",
                    "log_voucher_expired"
                ).format(id=voucher.voucher_id, code=voucher.activation_code),
                log_lvl=LogLevel.INFO
            )

        else:
            if limit_reached: # если достигли лимита по активациям
                message_user = get_text(
                    language,
                    "discount",
                    "voucher_reached_activation_limit"
                ).format(id=voucher.voucher_id, code=voucher.activation_code)
            else: # если достигли лимита по времени
                message_user = get_text(
                    language,
                    "discount",
                    "voucher_expired_due_to_time"
                ).format(id=voucher.voucher_id, code=voucher.activation_code)

            await self.tg_client.send_message(user_id, message_user)

    async def _set_not_valid_promo_code(self, data_time_to: datetime) -> None:
        invalid_promo_codes = await self.promo_code_repo.get_not_valid_promo_codes(data_time_to)

        for promo in invalid_promo_codes:
            await self.promo_code_service.deactivate_promo_code(promo_code_id=promo.promo_code_id)

    async def _set_not_valid_vouchers(self, data_time_to: datetime) -> None:
        invalid_vouchers = await self.voucher_repo.get_not_valid_voucher(data_time_to)

        for voucher in invalid_vouchers:
            await self.voucher_service.deactivate_voucher(voucher.voucher_id)
            user = await self.user_service.get_user(voucher.creator_id)
            await self._send_set_not_valid_voucher(voucher.creator_id, voucher, False, user.language)