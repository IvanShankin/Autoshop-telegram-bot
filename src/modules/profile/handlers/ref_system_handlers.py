from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile

from src.infrastructure.telegram.bot_instance import get_bot
from src.modules.profile.keyboards import ref_system_kb, accrual_ref_list_kb, back_in_ref_system_kb
from src.modules.profile.services.profile_message import message_income_ref, message_ref_system
from src.database.models.users import Users
from src.services.bot import Messages
from src.services.models.modules import ProfileModule
from src.utils.i18n import get_text

router_with_repl_kb = Router()
router = Router()


@router.callback_query(F.data == "referral_system")
async def referral_system(
    callback: CallbackQuery, user: Users, profile_module: ProfileModule, messages_service: Messages
):
    bot = get_bot()
    bot_me = await bot.me()
    referrals = await profile_module.referral_service.get_all_referrals(user.user_id)
    ref_first_lvl = 0
    ref_second_lvl = 0

    for ref in referrals:
        if ref.level == 1:
            ref_first_lvl += 1
        elif ref.level == 2:
            ref_second_lvl += 1

    text = get_text(
        user.language,
        "profile_messages",
        "referral_info"
    ).format(
        ref_link=f'https://t.me/{bot_me.username}?start=ref_{user.unique_referral_code}',
        total_earnings=user.total_profit_from_referrals,
        total_number_ref=len(referrals),
        ref_first_lvl=ref_first_lvl,
        ref_second_lvl=ref_second_lvl
    )

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='ref_system',
        reply_markup=await ref_system_kb(user.language, user.user_id)
    )


@router.callback_query(F.data.startswith('accrual_ref_list:'))
async def accrual_ref_list(
    callback: CallbackQuery, user: Users, profile_module: ProfileModule, messages_service: Messages
):
    _,  target_user_id,  current_page = callback.data.split(':')

    await profile_module.permission_service.check_permission(user.user_id, int(target_user_id))

    text = get_text(
        user.language,
        "profile_messages",
        'referral_earnings_history'
    )

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='history_income_from_referrals',
        reply_markup= await accrual_ref_list_kb(
            user.language, int(current_page), int(target_user_id), user.user_id, profile_module
        )
    )


@router.callback_query(F.data.startswith('detail_income_from_ref:'))
async def detail_income_from_ref(
    callback: CallbackQuery, user: Users, profile_module: ProfileModule, messages_service: Messages
):
    income_from_ref_id = callback.data.split(':')[1]
    current_page = int(callback.data.split(':')[2])

    income = await profile_module.referral_income_service.get_income_from_referral(int(income_from_ref_id))

    if income is None:
        await callback.answer(text=get_text(user.language, "miscellaneous",'data_not_found'), show_alert=True)

    await profile_module.permission_service.check_permission(user.user_id, int(income.owner_user_id))

    await message_income_ref(
        income=income,
        callback=callback,
        language=user.language,
        current_page=current_page,
        messages_service=messages_service,
        profile_module=profile_module,
    )


@router.callback_query(F.data.startswith("download_ref_list:"))
async def download_ref_list(
    callback: CallbackQuery, user: Users, profile_module: ProfileModule
):
    user_id = int(callback.data.split(':')[1])

    await profile_module.permission_service.check_permission(user.user_id, user_id)

    data = await profile_module.referral_service.build_report_data(user_id)
    file_bytes = profile_module.excel_report_exporter.export(
        data=data,
        language=user.language,
        owner_user_id=user_id
    )

    filename = f"referrals_{user_id}.xlsx"

    await callback.message.answer_document(
        document=BufferedInputFile(file_bytes, filename=filename)
    )


@router.callback_query(F.data.startswith("ref_system_info"))
async def ref_system_info(
    callback: CallbackQuery, user: Users, profile_module: ProfileModule, messages_service: Messages
):
    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=await message_ref_system(user.language, profile_module),
        event_message_key="ref_system",
        reply_markup=back_in_ref_system_kb(user.language)
    )

