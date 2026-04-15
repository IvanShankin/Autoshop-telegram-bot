from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.infrastructure.telegram.bot_client import TelegramClient
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import admin_vouchers_kb, all_admin_vouchers_kb, \
    back_in_all_admin_voucher_kb, show_admin_voucher_kb

from src.utils.i18n import get_text


router = Router()


@router.callback_query(F.data == "admin_vouchers")
async def admin_vouchers(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages):
    await state.clear()
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=admin_vouchers_kb(user.language)
    )


@router.callback_query(F.data.startswith("admin_voucher_list:"))
async def admin_voucher_list(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages
):
    current_page = callback.data.split(":")[1]

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        event_message_key='admin_panel',
        reply_markup=await all_admin_vouchers_kb(
            current_page=int(current_page),
            language=user.language,
            admin_module=admin_module,
        )
    )


@router.callback_query(F.data.startswith("show_admin_voucher:"))
async def show_admin_voucher(
    callback: CallbackQuery,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    current_page = int(callback.data.split(':')[1])
    voucher_id = int(callback.data.split(":")[2])

    voucher = await admin_module.voucher_service.get_voucher_by_id(voucher_id)

    if not voucher:
        text = get_text(user.language, "profile_messages", "voucher_currently_inactive")
        reply_markup=back_in_all_admin_voucher_kb(user.language, current_page)
    else:
        bot_me = await tg_client.me()
        text = get_text(
            user.language,
            "admins_editor_vouchers",
            "voucher_details"
        ).format(
            id=voucher_id,
            valid=voucher.is_valid,
            link=f'https://t.me/{bot_me.username}?start=voucher_{voucher.activation_code}',
            total_amount=voucher.amount * voucher.number_of_activations if voucher.number_of_activations else f"{voucher.amount} +",
            amount=voucher.amount,
            number_of_activations=(voucher.number_of_activations if voucher.number_of_activations  else
                                   get_text(user.language, "admins_editor_vouchers", "unlimited")),
            activated_counter=voucher.activated_counter,
            start_at=voucher.start_at.strftime(admin_module.conf.different.dt_format),
            expire_at= (voucher.expire_at.strftime(admin_module.conf.different.dt_format) if voucher.expire_at else
                        get_text(user.language, "admins_editor_vouchers", "endlessly"))
        )
        reply_markup = show_admin_voucher_kb(
            language=user.language,
            current_page=current_page,
            voucher_id=voucher_id
        )

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='admin_panel',
        reply_markup=reply_markup
    )