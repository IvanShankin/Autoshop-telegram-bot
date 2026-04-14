from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter
from aiogram.types import Message, TelegramObject, CallbackQuery

from typing import Callable, Dict, Any, Awaitable, Type

from src.application.bot import Messages
from src.containers.app_container import AppContainer
from src.application.models.modules import AdminModule
from src.infrastructure.telegram.ui.keyboard import support_kb
from src.utils.i18n import get_text


class ModulesMiddleware(BaseMiddleware):
    def __init__(self, app_container: AppContainer):
        self.app_container = app_container

    async def __call__(self, handler, event, data):
        async_session_factory = self.app_container.conf.db_connection.session_local

        async with async_session_factory() as session:
            request_container = self.app_container.get_request_container(session)

            data["profile_module"] = request_container.get_profile_modul()
            data["catalog_modul"] = request_container.get_catalog_modul()
            data["admin_modul"] = request_container.get_admin_modul()
            data["messages_service"] = request_container.get_message_service()
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
            admin_modul: AdminModule = data["admin_modul"]
            user = await admin_modul.user_service.get_user(user_id, username, update_last_used=True)
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

        admin_modul: AdminModule = data["admin_modul"]
        messages_service: Messages = data["messages_service"]
        # Проверяем режим обслуживания
        settings = await admin_modul.settings_service.get_settings()
        if not settings.maintenance_mode:
            return await handler(event, data)

        if await admin_modul.admin_service.check_admin(user_id):
            return await handler(event, data)

        user = await admin_modul.user_service.get_user(user_id, update_last_used=True)
        language = user.language if user else admin_modul.conf.app.default_lang

        await messages_service.send_msg.send(
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

        admin_modul: AdminModule = data["admin_modul"]
        messages_service: Messages = data["messages_service"]
        reason = await admin_modul.banned_account_service.get_ban(user.id)

        if reason:
            user_db = await admin_modul.user_service.get_user(user.id)
            message = f"Вы были забанены в боте по причине: {reason}"

            if user_db:
                message = get_text(user_db.language, "kb_start", "you_banned").format(reason=reason)

            settings = await admin_modul.settings_service.get_settings()
            await messages_service.send_msg.send(
                user.id, message=message, reply_markup=await support_kb(admin_modul.conf.app.default_lang, settings.support_username)
            )

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

        admin_modul: AdminModule = data["admin_modul"]
        if not await admin_modul.admin_service.check_admin(user.id):
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
            admin_modul: AdminModule = data["admin_modul"]
            user = await admin_modul.user_service.get_user(message.from_user.id, update_last_used=True)
        except Exception:
            return False

        if not user:
            return False

        return message.text == get_text(user.language, "kb_start", self.key)