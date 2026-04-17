from datetime import datetime, timezone
from logging import Logger

import aio_pika
import orjson


class RabbitMQProducer:

    def __init__(
        self,
        url: str,
        logger: Logger,
        exchange_name: str = "events",
    ):
        self.url = url
        self.logger = logger
        self.exchange_name = exchange_name

        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self):
        """Инициализация (вызывать один раз при старте приложения)"""
        self._connection = await aio_pika.connect_robust(self.url)

        self._channel = await self._connection.channel()

        self._exchange = await self._channel.declare_exchange(
            self.exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        self.logger.info("RabbitMQ connected")

    async def close(self):
        """Закрытие при shutdown"""
        if self._connection:
            await self._connection.close()
            self.logger.info("RabbitMQ connection closed")

    async def publish(self, event_data: dict, routing_key: str):
        if not self._exchange:
            raise RuntimeError("RabbitMQProducer not initialized")

        data = {
            "event": routing_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": event_data,
        }

        message = aio_pika.Message(
            body=orjson.dumps(data),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self._exchange.publish(message, routing_key=routing_key)