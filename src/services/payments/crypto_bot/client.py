import json

from aiocryptopay import AioCryptoPay, Networks

from src.bot_actions.messages import send_log
from src.config import TOKEN_CRYPTO_BOT, PAYMENT_LIFETIME_SECONDS
from src.services.database.replenishments_event.schemas import NewReplenishment
from src.services.database.users.actions import create_replenishment, update_replenishment
from src.services.redis.core_redis import get_redis
from src.utils.core_logger import logger


class CryptoPayService:
    def __init__(self, token: str, testnet: bool = False):
        self.client = AioCryptoPay(token, network=Networks.TEST_NET if testnet else Networks.MAIN_NET)

    async def create_invoice(self, user_id: int, type_payment_id, origin_amount_rub: int, amount_rub: int) -> str | None:
        """
        :param origin_amount_rub: Сумма без комиссии в рублях (её начислим).
        :param amount_rub: Сумма для пополнения в рублях (её возьмём с пользователя)
        :return: url для оплаты, если ничего не вернулось, то произошла ошибка(отошлёт лог в канал)
        """
        async with get_redis() as session_redis:
            rate = float(await session_redis.get("dollar_rate"))
            amount_usd = round(amount_rub / rate, 5)

        # создание в БД
        replenishment = await create_replenishment(
            user_id=user_id,
            type_payment_id=type_payment_id,
            origin_amount_rub=origin_amount_rub,
            amount_rub=amount_rub,
        )
        new_replenishment = NewReplenishment(
            replenishment_id = replenishment.replenishment_id,
            user_id = user_id,
            origin_amount = replenishment.origin_amount,
            amount = amount_rub
        )

        try:
            # создание счёта
            invoice = await self.client.create_invoice(
                amount=amount_usd,
                currency_type='fiat',
                fiat="USD",
                payload=json.dumps(new_replenishment.model_dump()), # поменять
                expires_in=PAYMENT_LIFETIME_SECONDS
            )
            # обновление в БД
            await update_replenishment(
                replenishment_id=replenishment.replenishment_id,
                status=replenishment.status,
                payment_system_id=str(invoice.invoice_id),
                invoice_url=invoice.bot_invoice_url,
            )
            return invoice.bot_invoice_url
        except Exception as e:
            text = (
                f"#Ошибка_при_создание_счёта_в_КБ \n"
                f"Ошибка: {str(e)} \n"
                f"Данные от пользователя: \n"
                f"Сумма в рублях: {amount_rub}\n"
                f"Сумма в долларах: {amount_usd}\n"
            )
            logger.error(text)
            await send_log(text)

            # обновление в БД
            await update_replenishment(
                replenishment_id=replenishment.replenishment_id,
                status='error',
            )

crypto_bot = CryptoPayService(token=TOKEN_CRYPTO_BOT,  testnet=False)
