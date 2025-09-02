import asyncio

from sqlalchemy import event
from sqlalchemy.orm import Session
from typing import Awaitable, Callable, List, Tuple
from src.utils.core_logger import logger

# глобальная очередь для хранения событий
event_queue: asyncio.Queue = asyncio.Queue()

# ключ для хранения отложенных событий в session.info
_SESSION_EVENTS_KEY = "_deferred_events"

Subscriber = Callable[[object], Awaitable[None]]
_subscribers: List[Tuple[int, Subscriber]] = [] # список событий и их приоритетов

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
    """После успешного commit() отправляем события в очередь."""
    events = pop_deferred_events(session) # удаляем вся события
    if not events:
        return

    loop = asyncio.get_running_loop() # получаем текущий
    for e in events:
        # кладёт событие в асинхронную очередь -> запускается обработка событий
        loop.call_soon_threadsafe(event_queue.put_nowait, e)



def subscribe(handler: Subscriber, priority: int = 0) -> None:
    """
    :param handler: Функция, которая добавит её для вызова в дальнейшем при совершении события.
    :param priority: Приоритет события (чем меньше число, тем раньше вызов).
    Событие с одинаковым приоритетом вызывается одновременно.
    """
    _subscribers.append((priority, handler))
    _subscribers.sort(key=lambda x: x[0]) # поддерживаем сортировку один раз при добавлении

async def run_dispatcher() -> None:
    """Прослушивает очередь из событий и запускает все функции из _subscribers передавая туда событие."""
    while True:
        event = await event_queue.get()

        try:
            if event is None:
                return

            # группируем подписчиков по приоритету
            current_priority = None
            coros = []
            for priority, handler in _subscribers:
                if current_priority is None:
                    current_priority = priority

                # если приоритет сменился — запускаем предыдущую группу
                if priority != current_priority:
                    results = await asyncio.gather(*coros, return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception):
                            logger.error(f"Ошибка в обработчике: {r}")

                    # начинаем новую группу
                    coros = []
                    current_priority = priority

                coros.append(handler(event))

            # добиваем последнюю группу
            if coros:
                results = await asyncio.gather(*coros, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        logger.error(f"Ошибка в обработчике: {r}")
        finally:
            event_queue.task_done()
