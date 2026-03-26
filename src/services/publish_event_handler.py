from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.infrastructure.rebbit_mq.producer import publish_event


class PublishEventHandler:

    @classmethod
    async def ban_account(cls, admin_id: int, user_id: int, reason: str):
        event = EventSentLog(
            text=(
                f"🛠️\n"
                f"#Аккаунт_забанен \n\n"
                f"Админ c ID = '{admin_id}' \n"
                f"Добавил нового пользователя в забаненные аккаунты \n\n"
                f"ID Пользователя: '{user_id}'\n"
                f"Причина: '{reason}'"
            ),
            log_lvl=LogLevel.INFO
        )
        await publish_event(event.model_dump(), "message.send_log")

    @classmethod
    async def delete_ban_account(cls, admin_id: int, user_id: int):
        event = EventSentLog(
            text=(
                f"🛠️\n"
                f"#Аккаунт_разбанен \n\n"
                f"Админ c ID = '{admin_id}' разбанил пользователя \n"
                f"ID разбаненного аккаунта: '{user_id}'"
            ),
            log_lvl=LogLevel.INFO
        )
        await publish_event(event.model_dump(), "message.send_log")

    @classmethod
    async def admin_update_balance(
        cls,
        admin_id: int,
        target_user_id: int,
        balance_before: int,
        balance_after: int
    ):
        event = EventSentLog(
            text=(
                f"🔴\n"
                f"#Админ_изменил_баланс_пользователю \n\n"
                f"ID админа: {admin_id}\n"
                f"ID пользователя: {target_user_id}\n\n"
                f"Баланс до: {balance_before}\n"
                f"Баланс после: {balance_after}\n"
                f"Изменён на: {balance_before - balance_after}\n"
                f"🔴"
            ),
            log_lvl=LogLevel.INFO
        )
        await publish_event(event.model_dump(), "message.send_log")