from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware

from src.services.database.database import session_local


class DataBaseSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        async with session_local() as session:
            data["db"] = session   # db будет доступен в хендлерах
            return await handler(event, data)


# пример как взять использовать в роутере
# from aiogram import Router
# from src.middlewares.database import DataBaseSessionMiddleware
# router = Router()
# router.message.middleware(DataBaseSessionMiddleware())
# @router.message()
# async def test_handler(message: types.Message, db: AsyncSession):