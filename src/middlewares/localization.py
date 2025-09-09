from aiogram import BaseMiddleware

from src.database.action_main_models import get_user
from src.i18n import make_gettext

class LocalizationMiddleware(BaseMiddleware):
    async def on_pre_process_update(self, update, data: dict):
        user_id = None
        # пример: для сообщения
        if getattr(update, "message", None):
            user_id = update.message.from_user.id
        # ... другие типы update

        lang = "ru"
        if user_id:
            user = await get_user(user_id)
            if user and user.language:
                lang = user.language

        # кладём в data функцию перевода и код языка
        data["lang"] = lang
        data["_"] = make_gettext(lang)
