from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot_actions.actions import send_message, edit_message
from src.bot_actions.bot_instance import get_bot
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.profile.keyboard_profile import profile_kb
from src.services.discounts.actions import get_valid_voucher_by_user
from src.services.users.actions import get_user
from src.utils.i18n import get_i18n

router_with_repl_kb = Router()
router = Router()


async def handler_profile(
        user_id: int,
        username: str | None,
        send_new_message: bool = True,
        chat_id: int = None,
        message_id: int = None
):
    user = await get_user(user_id, username)
    i18n = get_i18n(user.language, 'profile_messages')
    username = i18n.gettext('No') if  user.username is None else f'@{user.username}'

    bot = await get_bot()
    bot_me = await bot.me()
    vouchers = await get_valid_voucher_by_user(user_id)

    money_in_vouchers = 0
    for voucher in vouchers:
        money_in_vouchers += voucher.amount

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext(
        "Username: {username} \nID: {id} \nRef_link: {ref_link} \nTotal sum replenishment: {total_sum_replenishment}"
        "\nBalance: {balance}, \nMoney in vouchers {money_in_vouchers}"
    ).format(
        username = username,
        id = user.user_id,
        ref_link = f'https://t.me/{bot_me.username}?start=ref_{user.unique_referral_code}',
        total_sum_replenishment = user.total_sum_replenishment,
        balance = user.balance,
        money_in_vouchers = money_in_vouchers,
    )

    if send_new_message:
        await send_message(chat_id=user_id, message=text, image_key="profile", reply_markup=profile_kb(user.language))
    else:
        await edit_message(
            chat_id=chat_id,
            message_id=message_id,
            message=text,
            image_key='profile',
            reply_markup=profile_kb(user.language)
        )

@router_with_repl_kb.message(I18nKeyFilter("Profile"))
async def handle_profile_message(message: Message, state: FSMContext):
    await state.clear()
    await handler_profile(user_id=message.from_user.id, username=message.from_user.username)

@router.callback_query(F.data == "profile")
async def handle_profile_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await handler_profile(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        send_new_message=False,
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id
    )
