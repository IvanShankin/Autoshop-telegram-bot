from logging import Logger

import orjson

from src.config import Config
from src.database.models.system.models import ReplenishmentService
from src.exceptions.business import IncorrectedReplenishmentService
from src.infrastructure.crypto_bot.core import CryptoProvider
from src.models.create_models.users import CreateReplenishmentDTO
from src.models.read_models.events.message import LogLevel
from src.models.update_models.users import UpdateReplenishment
from src.repository.redis import DollarRateRepository
from src.services.events.publish_event_handler import PublishEventHandler
from src.services.models.systems import TypesPaymentsService
from src.services.models.users import ReplenishmentsService, UserService


class PaymentService:
    def __init__(
        self,
        replenishments_service: ReplenishmentsService,
        publish_event_handler: PublishEventHandler,
        types_payments_service: TypesPaymentsService,
        user_service: UserService,
        dollar_rate_repo: DollarRateRepository,
        crypto_provider: CryptoProvider,
        conf: Config,
        logger: Logger,
    ):
        self.replenishments_service = replenishments_service
        self.publish_event_handler = publish_event_handler
        self.types_payments_service = types_payments_service
        self.user_service = user_service
        self.dollar_rate_repo = dollar_rate_repo
        self.crypto_provider = crypto_provider
        self.conf = conf
        self.logger = logger

    async def _create_invoice_cb(self, amount_usd: float, payload: str, expires_in: int) -> tuple[str, str]:
        """
        :return: (invoice_id, invoice_url)
        """
        return await self.crypto_provider.create_invoice(
            amount_usd=amount_usd,
            payload=payload,
            expires_in=expires_in,
        )

    async def create(
        self,
        user_id: int,
        type_payment_id: int,
        origin_amount_rub: int,
        amount_rub: int,
        service: ReplenishmentService
    ) -> str:
        """
        :param origin_amount_rub: Сумма без комиссии в рублях (её начислим).
        :param amount_rub: Сумма для пополнения в рублях (её возьмём с пользователя)
        :return: url для оплаты, если ничего не вернулось, то произошла ошибка(отошлёт лог в канал)
        :except IncorrectedReplenishmentService
        """

        rate = await self.dollar_rate_repo.get()
        rate = rate if rate else 80
        amount_usd = round(amount_rub / rate, 5)

        # создание в БД
        new_replenishment = await self.replenishments_service.create_replenishment(
            user_id=user_id,
            type_payment_id=type_payment_id,
            data=CreateReplenishmentDTO(
                origin_amount=origin_amount_rub,
                amount=amount_rub,
                service=service,
            ),
            make_commit=True,
        )

        try:
            if service == ReplenishmentService.CRYPTO_BOT:
                invoice_id, invoice_url = await self._create_invoice_cb(
                    amount_usd=amount_usd,
                    payload=orjson.dumps(new_replenishment.model_dump()).decode("utf-8"),
                    expires_in=self.conf.different.payment_lifetime_seconds,
                )
            # при расширении добавить новые проверки
            else:
                raise IncorrectedReplenishmentService()


            await self.replenishments_service.update_replenishment(
                replenishment_id=new_replenishment.replenishment_id,
                data=UpdateReplenishment(
                    payment_system_id=invoice_id,
                    invoice_url=invoice_url,
                ),
                make_commit=True,
            )
            return invoice_url
        except Exception as e:
            text = (
                f"#Ошибка_при_создание_счёта \n"
                f"Ошибка: {str(e)} \n"
                f"Данные от пользователя: \n"
                f"Сумма в рублях: {amount_rub}\n"
                f"Сумма в долларах: {amount_usd}\n"
                f"Сервис оплаты: {service.value}\n"
            )
            self.logger.exception(
                "Invoice creation failed",
                extra={
                    "user_id": user_id,
                    "amount_rub": amount_rub,
                    "service": service.value
                }
            )

            await self.publish_event_handler.send_log(
                text=text,
                log_lvl=LogLevel.ERROR
            )

            await self.replenishments_service.update_replenishment(
                replenishment_id=new_replenishment.replenishment_id,
                data=UpdateReplenishment(status="error"),
                make_commit=True,
            )
