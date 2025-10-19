import asyncio
from contextlib import suppress

import aio_pika
import aiormq
from orjson import orjson

from src.config import RABBITMQ_URL
from src.services.discounts.events import promo_code_event_handler, voucher_event_handler
from src.services.referrals.events import referral_event_handler
from src.services.replenishments_event.event_handlers_replenishments import replenishment_event_handler
from src.services.selling_accounts.events.even_handlers_acc import account_purchase_event_handler
from src.utils.core_logger import logger

# глобальные переменные для управления задачей
_consumer_task: asyncio.Task | None = None
_consumer_start_event: asyncio.Event | None = None
_consumer_stop_event: asyncio.Event | None = None

async def start_background_consumer():
    global _consumer_task, _consumer_stop_event, _consumer_start_event

    if _consumer_task and not _consumer_task.done():
        return  # уже запущен

    _consumer_start_event = asyncio.Event()
    _consumer_stop_event = asyncio.Event()
    _consumer_task = asyncio.create_task(_consumer_runner(_consumer_start_event, _consumer_stop_event))

    def on_done(task: asyncio.Task):
        try:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                logger.error("Consumer task crashed: %s", exc)
        except asyncio.CancelledError:
            # Нормальное завершение
            pass
        except Exception as e:
            logger.error("Error while checking consumer task: %s", e)

    _consumer_task.add_done_callback(on_done)
    logger.info("Consumer started")


async def stop_background_consumer():
    global _consumer_task, _consumer_stop_event

    if not _consumer_task:
        return

    logger.info("Stopping consumer...")

    _consumer_stop_event.set()

    try:
        await asyncio.wait_for(_consumer_task, timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("Consumer didn't stop in time, cancelling...")
        _consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await _consumer_task
    except asyncio.CancelledError:
        # это штатно при закрытии
        pass

    _consumer_task = None
    _stop_event = None
    logger.info("Consumer stopped cleanly")

async def _consumer_runner(started_event: asyncio.Event, stop_event: asyncio.Event):
    """
    Запускает цикл, который поддерживает подключение к RabbitMQ.
    При ошибке — логируем и переподключаемся через паузу.
    """
    reconnect_delay = 1.0
    while not stop_event.is_set():
        try:
            await _run_single_consumer_loop(started_event, stop_event)
            # если loop корректно завершился (например stop_event установился) — выйти
            break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Consumer crashed, will reconnect in %s seconds", reconnect_delay)
            await asyncio.sleep(reconnect_delay)


async def _run_single_consumer_loop(started_event: asyncio.Event, stop_event: asyncio.Event):
    """
    Одна сессия: соединяемся, объявляем exchange/queue/binds, регистрируем consumer и
    обрабатываем сообщения, пока stop_event не установлен.
    """
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    try:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("events", aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue("events_db", durable=True, exclusive=False, auto_delete=False)

        routing_keys = ["promo_code.*", "voucher.*", "referral.*", "replenishment.*", "account.*"]

        for key in routing_keys:
            await queue.bind(exchange, routing_key=key)

        started_event.set()

        # локальная очередь для передачи сообщений из callback в обработчик
        message_queue: asyncio.Queue[aio_pika.IncomingMessage] = asyncio.Queue()

        async def on_message(message: aio_pika.IncomingMessage):
            # не делать тяжёлую работу в callback // просто передаём в очередь
            await message_queue.put(message)

        consumer_tag = await queue.consume(on_message, no_ack=False)

        try:
            while not stop_event.is_set():
                try:
                    message: aio_pika.IncomingMessage = await asyncio.wait_for(message_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                # обрабатываем сообщение
                try:
                    async with message.process():
                        event = orjson.loads(message.body)
                        await handle_event(event)
                except Exception:
                    logger.exception("Ошибка при обработке сообщения")
        finally:
            logger.info("Cancelling consumer %s", consumer_tag)
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
        elif event["event"].startswith("account."):
            await account_purchase_event_handler(event)

    except aiormq.exceptions.ChannelInvalidStateError as e:
        logger.error(f"Ошибка при обращении с каналом! {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения у RebbitMQ. Ошибка: {str(e)}")

