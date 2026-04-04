from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter
from aiogram.types import Message, TelegramObject, CallbackQuery

from typing import Callable, Dict, Any, Awaitable, Type

from src.bot_actions.bot_instance import get_bot, get_bot_logger
from src.bot_actions.messages import send_message
from src.config import get_config
from src.container import init_container
from src.infrastructure.telegram.client import TelegramClient
from src.modules.keyboard_main import support_kb
from src.services._database.admins.actions import check_admin
from src.services._database.system.actions import get_settings
from src.services._database.users.actions import get_user, get_banned_account
from src.utils.i18n import get_text



class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async_session_factory = get_config().db_connection.session_local
        async with async_session_factory() as session_db:
            data["session_db"] = session_db
            return await handler(event, data)


class ModulesMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        session_db = data["session_db"]

        bot = get_bot()
        logger_bot = get_bot_logger()

        telegram_client = TelegramClient(bot=bot)
        telegram_logger_client = TelegramClient(bot=logger_bot)

        container = init_container(session_db, telegram_client, telegram_logger_client)

        data["profile_module"] = container.get_profile_modul()
        data["messages_service"] = container.get_message_service()
        # создание модулей под другие разделы
        return await handler(event, data)


class DeleteMessageOnErrorMiddleware(BaseMiddleware):
    def __init__(self, target_error: Type[Exception], text_message_answer: str):
        self.target_error = target_error
        self.text_message_answer = text_message_answer

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:

        try:
            return await handler(event, data)
        except self.target_error:
            # работаем только с callback_query
            if isinstance(event, CallbackQuery) and event.message:
                try:
                    await event.message.delete()
                except TelegramBadRequest:
                    pass

            # обязательно закрываем callback
            if isinstance(event, CallbackQuery):
                if self.text_message_answer:
                    await event.answer(self.text_message_answer)

            # ошибка считается обработанной
            return


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
        language = user.language if user else get_config().app.default_lang

        await send_message(
            user_id,
            message=get_text(
                language,
                "start_message",
                "temporarily_maintenance"
            ),
            event_message_key="technical_work"
        )


class CheckuserNotBlok(BaseMiddleware):
    """
        Проверит наличие бана у пользователя, если имеется, то отправит соответсвующее сообщение
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")

        if not user:
            return

        reason = await get_banned_account(user.id)
        if reason:
            user_db = await get_user(user.id)
            conf = get_config()
            message = f"Вы были забанены в боте по причине: {reason}"

            if user_db:
                message = get_text(user_db.language, "kb_start", "you_banned").format(reason=reason)

            await send_message(user.id, message=message, reply_markup=await support_kb(conf.app.default_lang))

            return

        return await handler(event, data)


class OnlyAdminsMiddleware(BaseMiddleware):
    """
    middleware который пропускает только админов (использовать для работы с админ панелью)
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")

        if not user:
            return

        if not await check_admin(user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("Access for administrators only", show_alert=True)
                await event.message.delete()
            return

        return await handler(event, data)


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

        return message.text == get_text(user.language, "kb_start", self.key)