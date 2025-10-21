from src.bot_actions.actions import send_message
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_i18n


async def checking_correctness_number(message: str, language: str, user_id: int, positive: bool, reply_markup) -> bool:
    """
    Проверяет, что message это число, если это не так, то отошлёт пользователю сообщение об это.
    :return Результат (Корректное число = True)
    """
    if not safe_int_conversion(message, positive=positive):
        i18n = get_i18n(language, 'miscellaneous')
        text = i18n.gettext('Incorrect value entered')
        await send_message(
            chat_id=user_id,
            message=text,
            image_key='incorrect_data_entered',
            reply_markup=reply_markup
        )
        return False
    return True

async def checking_availability_money(user_balance: int, need_money: int, language: str, user_id: int, reply_markup):
    """
    Проверяет, что у пользователя достаточно денег если это нет так, то отошлёт пользователю сообщение об это.
    :return Результат (Достаточно = True)
    """
    if user_balance < need_money:
        i18n = get_i18n(language, 'miscellaneous')
        text = i18n.gettext('Insufficient funds: {amount}').format(amount=need_money - user_balance)
        await send_message(
            chat_id=user_id,
            message=text,
            image_key='insufficient_funds',
            reply_markup=reply_markup
        )
        return False
    return True