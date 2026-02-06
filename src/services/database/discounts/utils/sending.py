from src.bot_actions.messages.schemas import LogLevel, EventSentLog
from src.broker.producer import publish_event
from src.services.database.discounts.models import Vouchers
from src.utils.i18n import get_text
from src.bot_actions.messages import send_log, send_message


async def send_set_not_valid_voucher(user_id: int, voucher: Vouchers, limit_reached: bool, language: str):
    """
    Отошлёт сообщение в канал или пользователю в зависимости от 'is_created_admin' в voucher
    :param user_id: id пользователя
    :param voucher: объект БД ваучера
    :param limit_reached: флаг получения лимита по активации
    :param language: язык пользователя
    :return:
    """
    if voucher.is_created_admin: # отсылка лога в канал
        event = EventSentLog(
            text=get_text(
                'ru',
                "discount",
                "log_voucher_expired"
            ).format(id=voucher.voucher_id, code=voucher.activation_code),
            log_lvl=LogLevel.INFO
        )
        await publish_event(event.model_dump(), "message.send_log")

    else:
        if limit_reached: # если достигли лимита по активациям
            message_user = get_text(
                language,
                "discount",
                "voucher_reached_activation_limit"
            ).format(id=voucher.voucher_id, code=voucher.activation_code)
        else: # если достигли лимита по времени
            message_user = get_text(
                language,
                "discount",
                "voucher_expired_due_to_time"
            ).format(id=voucher.voucher_id, code=voucher.activation_code)

        await send_message(user_id, message_user)