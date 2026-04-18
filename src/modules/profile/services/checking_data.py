from src.application.bot import Messages
from src.utils.converter import safe_int_conversion
from src.infrastructure.translations import get_text


async def checking_correctness_number(
    message: str,
    language: str,
    user_id: int,
    positive: bool,
    messages_service: Messages,
    reply_markup
) -> bool:
    """
    Проверяет, что message это число, если это не так, то отошлёт пользователю сообщение об это.
    :return Результат (Корректное число = True)
    """
    if not safe_int_conversion(message, positive=positive):
        text = get_text(language, "miscellaneous", "incorrect_value_entered")
        await messages_service.send_msg.send(
            chat_id=user_id,
            message=text,
            event_message_key='incorrect_data_entered',
            reply_markup=reply_markup
        )
        return False
    return True

async def checking_availability_money(
    user_balance: int,
    need_money: int,
    language: str,
    user_id: int,
    messages_service: Messages,
    reply_markup
):
    """
    Проверяет, что у пользователя достаточно денег если это нет так, то отошлёт пользователю сообщение об это.
    :return Результат (Достаточно = True)
    """
    if user_balance < need_money:
        text = get_text(language, "miscellaneous",'insufficient_funds').format(amount=need_money - user_balance)
        await messages_service.send_msg.send(
            chat_id=user_id,
            message=text,
            event_message_key='insufficient_funds',
            reply_markup=reply_markup
        )
        return False
    return True