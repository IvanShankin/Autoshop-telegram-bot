from datetime import datetime, timezone

import aio_pika
import orjson

from src.config import get_config


async def publish_event(event_data: dict, routing_key: str):
    connection = await aio_pika.connect_robust(get_config().env.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("events", aio_pika.ExchangeType.TOPIC, durable=True)

        data = {
          "event": routing_key,
          "timestamp": datetime.now(timezone.utc),
          "payload": event_data
        }

        message = aio_pika.Message(
            body=orjson.dumps(data),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        await exchange.publish(message, routing_key=routing_key)
