from aiogram import BaseMiddleware
from aiogram.filters import BaseFilter
from aiogram.types import Message, TelegramObject

from typing import Callable, Dict, Any, Awaitable

from src.bot_actions.messages import send_message
from src.config import DEFAULT_LANG
from src.services.database.admins.actions import check_admin
from src.services.database.system.actions import get_settings
from src.services.database.users.actions import get_user
from src.utils.i18n import get_text


class UserMiddleware(BaseMiddleware):
    """
    Универсальный middleware, который добавляет объект пользователя (User)
    в data для всех типов апдейтов, где есть from_user.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # aiogram сам парсит объект апдейта и кладёт ключи вроде "event_from_user"
        event_user = data.get("event_from_user")

        if event_user:
            user_id = event_user.id
            username = event_user.username

            # Получаем или создаём пользователя
            user = await get_user(user_id, username, update_last_used=True)
            data["user"] = user

        # даже если from_user нет, не ломаем обработку
        return await handler(event, data)


class MaintenanceMiddleware(BaseMiddleware):
    """
    Middleware для режима обслуживания (maintenance mode). Запрещает отправку сообщений от бота если идут тех работы.
    Администраторы смогут пользоваться ботом даже при техработах.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        event_user = data.get("event_from_user")

        user_id = event_user.id

        # Проверяем режим обслуживания
        settings = await get_settings()
        if not settings.maintenance_mode:
            return await handler(event, data)

        if await check_admin(user_id):
            return await handler(event, data)

        user = await get_user(user_id, update_last_used=True)
        language = user.language if user else DEFAULT_LANG

        await send_message(
            user_id,
            message=get_text(
                language,
                'start_message',
                "The bot is temporarily unavailable due to maintenance. Please try again later"
            ),
            image_key="technical_work"
        )


class I18nKeyFilter(BaseFilter):
    """Извлечёт i18n_key из I18nKeyResolverMiddleware"""
    def __init__(self, key: str):
        self.key = key

    async def __call__(self, message: Message, **data) -> bool:
        # сообщение должно содержать текст
        if not getattr(message, "text", None):
            return False
        try:
            user = await get_user(message.from_user.id, update_last_used=True)
        except Exception:
            return False

        if not user:
            return False

        return message.text == get_text(user.language, "keyboard", self.key)