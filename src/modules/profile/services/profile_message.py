from src.infrastructure.telegram.bot_instance import get_bot
from src.models.read_models import UsersDTO
from src.models.read_models.other import IncomeFromReferralsDTO
from src.modules.profile.keyboards import back_in_accrual_ref_list_kb
from src.services.bot import Messages
from src.services.models.module import ProfileModule
from src.utils.i18n import get_text


async def get_main_message_profile(user: UsersDTO, language: str, profile_module: ProfileModule) -> str:
    """
    Вернёт сообщение с данными о пользователе
    :param user: пользователя о котором будут выведены данные
    :param language: На каком языке вернуть сообщение. Для него отдельный параметр т.к. данная функция ещё используется для админа
    """
    username = get_text(language, "miscellaneous", 'no') if user.username is None else f'@{user.username}'

    bot = get_bot()
    bot_me = await bot.me()
    vouchers = await profile_module.voucher_service.get_valid_voucher_by_page(user.user_id)

    money_in_vouchers = 0
    for voucher in vouchers:
        money_in_vouchers += voucher.amount * (voucher.number_of_activations - voucher.activated_counter)

    return get_text(
        language,
        "profile_messages",
        "profile_info"
    ).format(
        username=username,
        id=user.user_id,
        ref_link=f'https://t.me/{bot_me.username}?start=ref_{user.unique_referral_code}',
        total_sum_replenishment=user.total_sum_replenishment,
        balance=user.balance,
        money_in_vouchers=money_in_vouchers,
    )


async def message_income_ref(
    income: IncomeFromReferralsDTO,
    callback, language: str,
    current_page: int,
    messages_service: Messages,
    profile_module: ProfileModule,
):
    referral_user = await profile_module.user_service.get_user(income.referral_id)
    username = f"@{referral_user.username}" if referral_user.username else 'None'

    text = get_text(
        language,
        "profile_messages",
        "referral_income_details"
    ).format(
        id=income.income_from_referral_id,
        username=username,
        amount=income.amount,
        percentage_of_replenishment=income.percentage_of_replenishment,
        date=income.created_at.strftime(profile_module.conf.different.dt_format),
    )

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='history_income_from_referrals',
        reply_markup= back_in_accrual_ref_list_kb(language, current_page, income.owner_user_id)
    )


async def message_ref_system(language: str, profile_module: ProfileModule,) -> str:
    text = get_text(
        language,
        "referral_messages",
        "referral_system_faq"
    )

    ref_lvls = await profile_module.referral_levels_service.get_referral_levels()
    length_list = len(ref_lvls)
    for i in range(len(ref_lvls)):
        if i == 0: # если это первый уровень
            text += get_text(
                language,
                "referral_messages",
                "referral_level_info_up_to"
            ).format(
                number_lvl=ref_lvls[i].level,
                amount_up_to=ref_lvls[i + 1].amount_of_achievement,
                percent=ref_lvls[i].percent
            )

        if i + 1 > length_list: # если есть после данного уровня ещё уровни
            text += get_text(
                language,
                "referral_messages",
                "referral_level_info_from_to"
            ).format(
                number_lvl=ref_lvls[i].level,
                amount_from=ref_lvls[i].amount_of_achievement,
                amount_up_to=ref_lvls[i + 1].amount_of_achievement,
                percent=ref_lvls[i].percent
            )

        if i + 1 == length_list: # если данный уровень последний
            text += get_text(
                language,
                "referral_messages",
                "referral_level_info_from"
            ).format(
                number_lvl=ref_lvls[i].level,
                amount_from=ref_lvls[i].amount_of_achievement,
                percent=ref_lvls[i].percent
            )

    return text
