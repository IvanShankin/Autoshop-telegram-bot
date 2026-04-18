from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import back_in_user_management_kb, \
    confirm_remove_ban_kb
from src.modules.admin_actions.schemas import SetNewBalanceData, IssueBanData
from src.modules.admin_actions.state import SetNewBalance, IssueBan
from src.utils.converter import safe_int_conversion
from src.infrastructure.translations import get_text


router = Router()

@router.callback_query(F.data.startswith("change_user_bal:"))
async def change_user_bal(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    target_user_id = int(callback.data.split(':')[1])
    target_user = await admin_module.user_service.get_user(target_user_id)
    await messages_service.edit_msg.edit(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "enter_new_balance_for_user"
        ).format(balance=target_user.balance),
        reply_markup=back_in_user_management_kb(user.language, target_user_id)
    )
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(SetNewBalance.new_balance)


@router.message(SetNewBalance.new_balance)
async def set_new_balance(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    data = SetNewBalanceData(**(await state.get_data()))
    new_balance = safe_int_conversion(message.text, positive=True)
    if new_balance:
        await admin_module.admin_service.admin_update_user_balance(
            admin_id=user.user_id, target_user_id=data.target_user_id, new_balance=new_balance
        )
        await state.clear()
        await messages_service.send_msg.send(
            user.user_id,
            get_text(
                user.language,
                "admins_user_mang",
                "balance_successfully_changed"
            ).format(balance=new_balance),
            reply_markup=back_in_user_management_kb(user.language, data.target_user_id)
        )
        return

    await messages_service.send_msg.send(
        user.user_id,
        get_text(user.language,"miscellaneous","incorrect_value_entered"),
        reply_markup=back_in_user_management_kb(user.language, data.target_user_id)
    )


@router.callback_query(F.data.startswith("issue_ban:"))
async def reason_issue_ban(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    target_user_id = int(callback.data.split(':')[1])
    await messages_service.edit_msg.edit(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "enter_reason_for_ban"
        ),
        reply_markup=back_in_user_management_kb(user.language, target_user_id)
    )
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(IssueBan.issue_ban)


@router.message(IssueBan.issue_ban)
async def issue_ban(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    data = IssueBanData(**(await state.get_data()))
    await admin_module.admin_service.create_banned_account(
        admin_id=user.user_id, user_id=data.target_user_id, reason=message.text
    )
    await messages_service.send_msg.send(
        user.user_id,
        get_text(user.language,"admins_user_mang","user_successfully_banned"),
        reply_markup=back_in_user_management_kb(user.language, data.target_user_id)
    )


@router.callback_query(F.data.startswith("confirm_remove_ban:"))
async def confirm_remove_ban(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages,
):
    target_user_id = int(callback.data.split(':')[1])
    await messages_service.edit_msg.edit(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "confirmation_unban_user"
        ),
        reply_markup=confirm_remove_ban_kb(user.language, target_user_id)
    )


@router.callback_query(F.data.startswith("remove_ban:"))
async def remove_ban(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    target_user_id = int(callback.data.split(':')[1])
    await admin_module.admin_service.delete_banned_account(admin_id=user.user_id, user_id=target_user_id)
    await messages_service.edit_msg.edit(
        user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_user_mang",
            "user_successfully_unbanned"
        ),
        reply_markup=back_in_user_management_kb(user.language, target_user_id)
    )


