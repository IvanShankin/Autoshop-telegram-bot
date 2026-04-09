import asyncio
import time
from collections import deque


class RateLimiter:
    """
    Позволяет ограничить число операций в единицу времени.
    max_calls: сколько вызовов разрешено
    period: за какое время (в секундах)
    """
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """
        Блокирует выполнение, пока не станет возможно сделать новый вызов.
        """
        async with self.lock:
            now = time.monotonic()

            # удалить старые вызовы
            while self.calls and (now - self.calls[0]) > self.period:
                self.calls.popleft()

            if len(self.calls) < self.max_calls:
                # можно сразу выполнять
                self.calls.append(now)
                return

            # иначе нужно подождать
            sleep_time = self.period - (now - self.calls[0])
            await asyncio.sleep(sleep_time)

            # после ожидания обновляем список
            now = time.monotonic()
            while self.calls and (now - self.calls[0]) > self.period:
                self.calls.popleft()

            self.calls.append(now)
