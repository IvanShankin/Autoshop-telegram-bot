from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import send_message, edit_message
from src.modules.admin_actions.keyboards import back_in_user_management_kb, \
    confirm_remove_ban_kb
from src.modules.admin_actions.schemas import SetNewBalanceData, IssueBanData
from src.modules.admin_actions.state import SetNewBalance, IssueBan
from src.services.database.users.actions import get_user, add_banned_account, delete_banned_account
from src.services.database.users.actions.action_user import admin_update_user_balance
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text


router = Router()

@router.callback_query(F.data.startswith("change_user_bal:"))
async def change_user_bal(callback: CallbackQuery, state: FSMContext, user: Users):
    target_user_id = int(callback.data.split(':')[1])
    target_user = await get_user(target_user_id)
    await edit_message(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "Enter a new balance for the user \n\nCurrent: {balance} ₽"
        ).format(balance=target_user.balance),
        reply_markup=back_in_user_management_kb(user.language, target_user_id)
    )
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(SetNewBalance.new_balance)


@router.message(SetNewBalance.new_balance)
async def set_new_balance(message: Message, state: FSMContext, user: Users):
    data = SetNewBalanceData(**(await state.get_data()))
    new_balance = safe_int_conversion(message.text, positive=True)
    if new_balance:
        await admin_update_user_balance(
            admin_id=user.user_id, target_user_id=data.target_user_id, new_balance=new_balance
        )
        await state.clear()
        await send_message(
            user.user_id,
            get_text(
                user.language,
                "admins_user_mang",
                "Balance successfully changed \n\nCurrent balance {balance}"
            ).format(balance=new_balance),
            reply_markup=back_in_user_management_kb(user.language, data.target_user_id)
        )
        return

    await send_message(
        user.user_id,
        get_text(user.language,"miscellaneous","Incorrect value entered"),
        reply_markup=back_in_user_management_kb(user.language, data.target_user_id)
    )


@router.callback_query(F.data.startswith("issue_ban:"))
async def reason_issue_ban(callback: CallbackQuery, state: FSMContext, user: Users):
    target_user_id = int(callback.data.split(':')[1])
    await edit_message(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "Please provide a reason for the ban"
        ),
        reply_markup=back_in_user_management_kb(user.language, target_user_id)
    )
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(IssueBan.issue_ban)


@router.message(IssueBan.issue_ban)
async def issue_ban(message: Message, state: FSMContext, user: Users):
    data = IssueBanData(**(await state.get_data()))
    await add_banned_account(admin_id=user.user_id, user_id=data.target_user_id, reason=message.text)
    await send_message(
        user.user_id,
        get_text(user.language,"admins_user_mang","The user has been successfully banned"),
        reply_markup=back_in_user_management_kb(user.language, data.target_user_id)
    )


@router.callback_query(F.data.startswith("confirm_remove_ban:"))
async def confirm_remove_ban(callback: CallbackQuery, user: Users):
    target_user_id = int(callback.data.split(':')[1])
    await edit_message(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "Are you sure you want to unban this user?"
        ),
        reply_markup=confirm_remove_ban_kb(user.language, target_user_id)
    )


@router.callback_query(F.data.startswith("remove_ban:"))
async def remove_ban(callback: CallbackQuery, user: Users):
    target_user_id = int(callback.data.split(':')[1])
    await delete_banned_account(admin_id=user.user_id, user_id=target_user_id)
    await edit_message(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "The user has been successfully unbanned"
        ),
        reply_markup=back_in_user_management_kb(user.language, target_user_id)
    )


