from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile

from src.bot_actions.messages import edit_message
from src.bot_actions.bot_instance import get_bot
from src.modules.profile.keyboard_profile import ref_system_kb, accrual_ref_list_kb
from src.modules.profile.services.profile_message import message_income_ref
from src.services.database.referrals.actions.actions_ref import get_all_referrals, get_income_from_referral
from src.services.database.referrals.reports import generate_referral_report_excel
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router_with_repl_kb = Router()
router = Router()


@router.callback_query(F.data == "referral_system")
async def referral_system(callback: CallbackQuery, user: Users):
    bot = await get_bot()
    bot_me = await bot.me()
    referrals = await get_all_referrals(user.user_id)
    ref_first_lvl = 0
    ref_second_lvl = 0

    for ref in referrals:
        if ref.level == 1:
            ref_first_lvl += 1
        elif ref.level == 2:
            ref_second_lvl += 1

    text = get_text(
        user.language,
        'profile_messages',
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
        reply_markup=await ref_system_kb(user.language, user.user_id)
    )


@router.callback_query(F.data.startswith('accrual_ref_list:'))
async def accrual_ref_list(callback: CallbackQuery, user: Users):
    _,  target_user_id,  current_page = callback.data.split(':')

    text = get_text(
        user.language,
        'profile_messages',
        'A history of all referral earnings. To view a specific transaction, click on it'
    )

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='history_income_from_referrals',
        reply_markup= await accrual_ref_list_kb(user.language, int(current_page), int(target_user_id), user.user_id)
    )


@router.callback_query(F.data.startswith('detail_income_from_ref:'))
async def detail_income_from_ref(callback: CallbackQuery, user: Users):
    income_from_ref_id = callback.data.split(':')[1]
    current_page = int(callback.data.split(':')[2])
    income = await get_income_from_referral(int(income_from_ref_id))

    if income is None:
        await callback.answer(text=get_text(user.language, 'miscellaneous','Data not found'), show_alert=True)

    await message_income_ref(
        income=income,
        callback=callback,
        language=user.language,
        current_page=current_page,
    )


@router.callback_query(F.data.startswith("download_ref_list:"))
async def download_ref_list(callback: CallbackQuery, user: Users):
    user_id = int(callback.data.split(':')[1])

    bytes_data = await generate_referral_report_excel(user_id, user.language)
    filename = f"referrals_{user_id}.xlsx"

    text = get_text(user.language, 'profile_messages','The file was successfully generated')

    await callback.message.answer_document(
        document=BufferedInputFile(bytes_data, filename=filename)
    )
    await callback.answer(text)


