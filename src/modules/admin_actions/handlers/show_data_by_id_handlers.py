from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message
from src.modules.admin_actions.keyboards import back_in_show_data_by_id_kb, data_by_id_by_page_kb
from src.modules.admin_actions.schemas.show_data_by_id import CurrentPage
from src.modules.admin_actions.services.show_data_by_id import show_data_by_id_handler
from src.modules.admin_actions.state.show_data_by_id import ShowDataById
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router_with_repl_kb = Router()
router = Router()

async def set_state_and_request_id(callback: CallbackQuery, state: FSMContext, user: Users, need_state: State):
    current_page = int(callback.data.split(":")[1])

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_show_data_by_id", "enter_id"),
        reply_markup=back_in_show_data_by_id_kb(language=user.language, current_page=current_page)
    )

    await state.update_data(current_page=current_page)

    await state.set_state(need_state)


@router.callback_query(F.data.startswith("data_by_id:"))
async def show_data_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    current_page = int(callback.data.split(":")[1])
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='admin_panel',
        reply_markup=data_by_id_by_page_kb(language=user.language, current_page=current_page)
    )


@router.callback_query(F.data.startswith("replenishment_by_id:"))
async def show_replenishment_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.replenishment_by_id)


@router.callback_query(F.data.startswith("purchase_by_id:"))
async def show_purchase_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.purchase_by_id)


@router.callback_query(F.data.startswith("sold_account_by_id:"))
async def show_sold_account_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.sold_account_by_id)


@router.callback_query(F.data.startswith("sold_universal_by_id:"))
async def show_sold_universal_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.sold_universal_product_by_id)


@router.callback_query(F.data.startswith("voucher_by_id:"))
async def show_voucher_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.voucher_by_id)


@router.callback_query(F.data.startswith("activate_voucher_by_id:"))
async def show_activate_voucher_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.activate_voucher_by_id)


@router.callback_query(F.data.startswith("promo_code_by_id:"))
async def show_promo_code_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.promo_code_by_id)


@router.callback_query(F.data.startswith("promo_code_activation_by_id:"))
async def show_promo_code_activation_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.promo_code_activation_by_id)


@router.callback_query(F.data.startswith("referral_by_id:"))
async def show_referral_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.referral_by_id)


@router.callback_query(F.data.startswith("income_from_ref_by_id:"))
async def show_income_from_ref_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.income_from_ref_by_id)


@router.callback_query(F.data.startswith("transfer_money_by_id:"))
async def show_transfer_money_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.transfer_money_by_id)


@router.callback_query(F.data.startswith("wallet_transaction_by_id:"))
async def show_wallet_transaction_by_id(callback: CallbackQuery, state: FSMContext, user: Users):
    await set_state_and_request_id(callback, state, user, ShowDataById.wallet_transaction_by_id)


@router.message(
    StateFilter(
        ShowDataById.replenishment_by_id,
        ShowDataById.purchase_by_id,
        ShowDataById.sold_account_by_id,
        ShowDataById.sold_universal_product_by_id,
        ShowDataById.voucher_by_id,
        ShowDataById.activate_voucher_by_id,
        ShowDataById.promo_code_by_id,
        ShowDataById.promo_code_activation_by_id,
        ShowDataById.referral_by_id,
        ShowDataById.income_from_ref_by_id,
        ShowDataById.transfer_money_by_id,
        ShowDataById.wallet_transaction_by_id,
    )
)
async def show_data_by_id_router(message: Message, state: FSMContext, user: Users):
    data = CurrentPage(**(await state.get_data()))
    await show_data_by_id_handler(await state.get_state(), message.text, user, data.current_page)

