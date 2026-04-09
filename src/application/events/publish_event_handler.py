from src.models.event_models.discounts import NewActivationVoucher
from src.models.read_models import EventSentLog, LogLevel
from src.infrastructure.rabbit_mq.producer import publish_event
from src.application.filesystem.schemas import EventCreateUiImage


class PublishEventHandler:

    async def send_log(cls, text: str, log_lvl: LogLevel):
        event = EventSentLog(text=text, log_lvl=log_lvl)
        await publish_event(event.model_dump(), "message.send_log")

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

    async def error_message_effect(
        cls,
        message_effect_id: str,
    ):
        event = EventSentLog(
            text=f"Указан неверный message_effect_id: {message_effect_id}",
            log_lvl=LogLevel.WARNING
        )
        await publish_event(event.model_dump(), "message.send_log")

    async def create_ui_image(
        cls,
        ui_image_key: str,
    ):
        await publish_event(
            EventCreateUiImage(ui_image_key=ui_image_key).model_dump(),
            "filesystem.create_ui_image"
        )

    async def voucher_activated(cls, data: NewActivationVoucher):
        await publish_event(data.model_dump(), "voucher.activated")