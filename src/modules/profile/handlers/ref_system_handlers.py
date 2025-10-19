import os

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

from src.bot_actions.actions import edit_message
from src.bot_actions.bot_instance import get_bot
from src.config import DT_FORMAT
from src.modules.profile.keyboard_profile import ref_system_kb, accruals_history_kb, back_in_accrual_history_kb
from src.services.referrals.actions.actions_ref import get_all_referrals, get_income_from_referral
from src.services.referrals.reports import generate_referral_report_exel
from src.services.users.actions import get_user
from src.utils.i18n import get_i18n

router_with_repl_kb = Router()
router = Router()


@router.callback_query(F.data == "referral_system")
async def referral_system(callback: CallbackQuery):
    bot = await get_bot()
    bot_me = await bot.me()
    user = await get_user(callback.from_user.id, callback.from_user.username)
    referrals = await get_all_referrals(user.user_id)
    ref_first_lvl = 0
    ref_second_lvl = 0

    for ref in referrals:
        if ref.level == 1:
            ref_first_lvl += 1
        elif ref.level == 2:
            ref_second_lvl += 1

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext(
        "Your referral link: <a href='{ref_link}'>Link</a> \n\n"
        "Total earnings: {total_earnings} \n"
        "Number of total invited referrals: {total_number_ref} \n"
        "Number of 1st level referrals: {ref_first_lvl} \n"
        "Number of 2nd level referrals: {ref_second_lvl} \n"
    ).format(
        ref_link=f'https://t.me/{bot_me.username}?start=ref_{user.unique_referral_code}',
        total_earnings=user.total_profit_from_referrals,
        total_number_ref=len(referrals),
        ref_first_lvl=ref_first_lvl,
        ref_second_lvl=ref_second_lvl
    )

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='ref_system',
        reply_markup=await ref_system_kb(user.language)
    )

@router.callback_query(F.data == "accrual_history_none")
async def referral_system(callback: CallbackQuery):
    await callback.answer("Список закончился")

@router.callback_query(F.data.startswith('accrual_history:'))
async def accrual_history(callback: CallbackQuery):
    user = await get_user(callback.from_user.id, callback.from_user.username)
    current_page = callback.data.split(':')[1]
    i18n = get_i18n(user.language, 'profile_messages')

    text = i18n.gettext('A history of all referral earnings. To view a specific transaction, click on it')

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='history_income_from_referrals',
        reply_markup= await accruals_history_kb(user.language, int(current_page), user.user_id)
    )


@router.callback_query(F.data.startswith('detail_income_from_ref:'))
async def detail_income_from_ref(callback: CallbackQuery):
    user = await get_user(callback.from_user.id, callback.from_user.username)
    income_from_ref_id = callback.data.split(':')[1]
    current_page = callback.data.split(':')[2]
    income = await get_income_from_referral(int(income_from_ref_id))

    if income is None:
        i18n = get_i18n(user.language, 'miscellaneous')
        await callback.answer(text=i18n.gettext('Data not found'), show_alert=True)

    referral_user = await get_user(income.referral_id)
    username = f"@{referral_user.username}" if referral_user.username else 'None'

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext(
        "ID: {id}\n\n"
        "Referral Username: {username}\n"
        "Amount: {amount}\n"
        "Percentage of Replenishment: {percentage_of_replenishment}\n"
        "Date: {date}\n"
    ).format(
        id=income.income_from_referral_id,
        username=username,
        amount=income.amount,
        percentage_of_replenishment=income.percentage_of_replenishment,
        date=income.created_at.strftime(DT_FORMAT),
    )

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='history_income_from_referrals',
        reply_markup= await back_in_accrual_history_kb(user.language, int(current_page))
    )


@router.callback_query(F.data == "download_ref_list")
async def download_ref_list(callback: CallbackQuery):
    user = await get_user(callback.from_user.id, callback.from_user.username)
    path = await generate_referral_report_exel(user.user_id, user.language)

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('The file was successfully generated')

    await callback.message.answer_document(FSInputFile(path))
    await callback.answer(text)

    os.remove(path)

