import asyncio
from contextlib import suppress
from logging import Logger
from typing import Optional, Callable, Awaitable

import aio_pika
import aiormq
from orjson import orjson

from src.config import Config


ROUTING_KEYS = [
    "promo_code.*",
    "voucher.*",
    "referral.*",
    "replenishment.*",
    "account.*",
    "purchase.*",
    "_filesystem.*",
    "message.*"
]


class RabbitMQConsumer:
    def __init__(
        self,
        event_handler: Callable[[dict], Awaitable[None]],
        conf: Config,
        logger: Logger,
    ):
        """
        :param event_handler: функция из сервисного слоя (dispatcher / use-case)
        """
        self._event_handler = event_handler

        self._consumer_task: Optional[asyncio.Task] = None
        self._consumer_start_event: Optional[asyncio.Event] = None
        self._consumer_stop_event: Optional[asyncio.Event] = None

        self.logger = logger
        self.conf = conf

    async def start(self):
        if self._consumer_task and not self._consumer_task.done():
            return

        self._consumer_start_event = asyncio.Event()
        self._consumer_stop_event = asyncio.Event()

        self._consumer_task = asyncio.create_task(
            self._consumer_runner(
                self._consumer_start_event,
                self._consumer_stop_event,
            )
        )

        self._consumer_task.add_done_callback(self._on_done)

        self.logger.info("Consumer started")

    async def stop(self):
        if not self._consumer_task:
            return

        self.logger.info("Stopping consumer...")

        self._consumer_stop_event.set()

        try:
            await asyncio.wait_for(self._consumer_task, timeout=10.0)
        except asyncio.TimeoutError:
            self.logger.warning("Consumer didn't stop in time, cancelling...")
            self._consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._consumer_task
        except asyncio.CancelledError:
            pass

        self._consumer_task = None
        self._consumer_stop_event = None

        self.logger.info("Consumer stopped cleanly")

    def _on_done(self, task: asyncio.Task):
        try:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                self.logger.error("Consumer task crashed: %s", exc)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error("Error while checking consumer task: %s", e)

    async def _consumer_runner(
        self,
        started_event: asyncio.Event,
        stop_event: asyncio.Event,
    ):
        reconnect_delay = 1.0

        while not stop_event.is_set():
            try:
                await self._run_single_consumer_loop(started_event, stop_event)
                break
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception(
                    "Consumer crashed, will reconnect in %s seconds",
                    reconnect_delay,
                )
                await asyncio.sleep(reconnect_delay)

    async def _run_single_consumer_loop(
        self,
        started_event: asyncio.Event,
        stop_event: asyncio.Event,
    ):
        connection = await aio_pika.connect_robust(
            self.conf.env.rabbitmq_url
        )

        try:
            channel = await connection.channel()

            exchange = await channel.declare_exchange(
                "events",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            queue = await channel.declare_queue(
                "events_db",
                durable=True,
                exclusive=False,
                auto_delete=False,
            )

            for key in ROUTING_KEYS:
                await queue.bind(exchange, routing_key=key)

            started_event.set()

            message_queue: asyncio.Queue[aio_pika.IncomingMessage] = asyncio.Queue()

            async def on_message(message: aio_pika.IncomingMessage):
                await message_queue.put(message)

            consumer_tag = await queue.consume(on_message, no_ack=False)

            try:
                while not stop_event.is_set():
                    try:
                        message: aio_pika.IncomingMessage = await asyncio.wait_for(
                            message_queue.get(),
                            timeout=0.5,
                        )
                    except asyncio.TimeoutError:
                        continue

                    await self._process_message(message)

            finally:
                self.logger.info("Cancelling consumer %s", consumer_tag)
                with suppress(Exception):
                    await queue.cancel(consumer_tag)

        finally:
            await connection.close()

    async def _process_message(self, message: aio_pika.IncomingMessage):
        try:
            async with message.process():
                event = orjson.loads(message.body)
                await self._event_handler(event)

        except aiormq.exceptions.ChannelInvalidStateError as e:
            self.logger.error(f"Ошибка при работе с каналом: {str(e)}")
        except Exception as e:
            self.logger.exception(
                f"Ошибка при обработке сообщения RabbitMQ: {str(e)}"
            )