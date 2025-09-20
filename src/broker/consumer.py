import asyncio
from contextlib import suppress

import aio_pika
import aiormq
from orjson import orjson

from src.config import RABBITMQ_URL
from src.services.discounts.events import promo_code_event_handler, voucher_event_handler
from src.services.referrals.events import referral_event_handler
from src.services.replenishments_event.event_handlers_replenishments import replenishment_event_handler
from src.utils.core_logger import logger

async def consume_events(started_event: asyncio.Event, stop_event: asyncio.Event):
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    try:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("events", aio_pika.ExchangeType.TOPIC, durable=True)

        queue = await channel.declare_queue("events_db", durable=True)
        await queue.bind(exchange, routing_key="promo_code.*")
        await queue.bind(exchange, routing_key="voucher.*")
        await queue.bind(exchange, routing_key="referral.*")
        await queue.bind(exchange, routing_key="replenishment.*")

        started_event.set()

        # используем asyncio.Queue для приёма сообщений
        message_queue: asyncio.Queue = asyncio.Queue()

        async def on_message(message: aio_pika.IncomingMessage):
            await message_queue.put(message)

        # подписываемся вручную
        consumer_tag = await queue.consume(on_message, no_ack=False)

        try:
            while not stop_event.is_set():
                try:
                    # ждём сообщение или выхода stop_event
                    message: aio_pika.IncomingMessage = await asyncio.wait_for(
                        message_queue.get(),
                        timeout=0.5  # проверяем stop_event каждые 0.5 сек
                    )
                except asyncio.TimeoutError:
                    continue

                try:
                    async with message.process():
                        event = orjson.loads(message.body)
                        await handle_event(event)
                except Exception as exc:
                    logger.exception("Ошибка обработки сообщения: %s", exc)

        finally:
            # отменяем consumer аккуратно
            with suppress(Exception):
                await queue.cancel(consumer_tag)

    finally:
        await connection.close()

async def handle_event(event: dict):
    try:
        if event["event"].startswith("promo_code."):
            await promo_code_event_handler(event)
        elif event["event"].startswith("voucher."):
            await voucher_event_handler(event)
        elif event["event"].startswith("referral."):
            await referral_event_handler(event)
        elif event["event"].startswith("replenishment."):
            await replenishment_event_handler(event)

    except aiormq.exceptions.ChannelInvalidStateError as e:
        logger.error(f"Ошибка при обращении с каналом! {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения у RebbitMQ. Ошибка: {str(e)}")

