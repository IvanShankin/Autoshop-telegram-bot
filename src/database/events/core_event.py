import asyncio

from sqlalchemy import event
from sqlalchemy.orm import Session
from typing import Awaitable, Callable, List
from src.utils.core_logger import logger

# глобальная очередь для хранения событий
event_queue: asyncio.Queue = asyncio.Queue()

# ключ для хранения отложенных событий в session.info
_SESSION_EVENTS_KEY = "_deferred_events"

Subscriber = Callable[[object], Awaitable[None]]
_subscribers: List[Subscriber] = []

def push_deferred_event(session, evt):
    """Хранит события в отложенном списке событий (session.info)."""
    # если в отложенном списке нет значений, то создаст пустой словарь по ключу _SESSION_EVENTS_KEY,
    session.info.setdefault(_SESSION_EVENTS_KEY, []).append(evt)

def pop_deferred_events(session):
    """Достаёт (и удаляет) список отложенных событий из session.info"""
    # Удаление (pop) гарантирует, что события не будут отправлены повторно при следующем after_commit для той же сессии
    return session.info.pop(_SESSION_EVENTS_KEY, [])

@event.listens_for(Session, "after_commit")
def session_after_commit(session: Session):
    """after_commit срабатывает только после успешного commit() транзакции"""
    events = pop_deferred_events(session) # удаляем вся события
    if not events:
        return

    loop = asyncio.get_running_loop() # получаем текущий
    for e in events:
        # кладёт событие в асинхронную очередь -> запускается обработка событий
        loop.call_soon_threadsafe(event_queue.put_nowait, e)



def subscribe(handler: Subscriber) -> None:
    """Принимает функцию, которая добавит её для вызова в дальнейшем при совершении события"""
    _subscribers.append(handler)

async def run_dispatcher() -> None:
    """Прослушивает очередь из событий и запускает все функции из _subscribers передавая туда событие."""
    while True:
        event = await event_queue.get()

        try:
            if event is None:
                return

            coros = [h(event) for h in _subscribers] # формирует вызов функций из _subscribers
            results = await asyncio.gather(*coros, return_exceptions=True) # вызывает все функции с coros, ждя их завершения
            # если произошла ошибка, которую не обработали, то она возникнет тут

            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"В обработчике произошла ошибка: {str(r)}")
        finally:
            event_queue.task_done()
