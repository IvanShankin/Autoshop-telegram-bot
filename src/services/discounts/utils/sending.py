from src.services.discounts.models import Vouchers
from src.utils.bot_instance import get_bot
from src.utils.i18n import get_i18n
from src.utils.send_messages import send_log


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
        i18n = get_i18n('ru', "replenishment_dom")
        message_log = i18n.gettext(
            "#Voucher_expired \nID '{id}' \nCode '{code}'"
            "\n\nThe voucher has expired due to reaching the number of activations or time limit. It is no longer possible to activate it"
        ).format(id=voucher.voucher_id, code=voucher.activation_code)
        await send_log(message_log)

    else:
        i18n = get_i18n(language, "replenishment_dom")
        if limit_reached: # если достигли лимита по активациям
            message_user = i18n.gettext(
                "Voucher has reached its activation limit \n\nID '{id}' \nCode '{code}' "
                "\n\nThe voucher has expired due to the activation limit. It can no longer be activated"
            ).format(id=voucher.voucher_id, code=voucher.activation_code)
        else: # если достигли лимита по времени
            message_user = i18n.gettext(
                "Voucher expired \n\nID '{id}' \nCode '{code}' \n\nVoucher expired due to time limit. It can no longer be activated"
            ).format(id=voucher.voucher_id, code=voucher.activation_code)

        bot = await get_bot()
        await bot.send_message(user_id, message_user)