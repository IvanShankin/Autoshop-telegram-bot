from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message, send_message
from src.config import get_config
from src.modules.profile.keyboards import confirm_del_acc_kb, login_details_kb
from src.modules.profile.keyboards.purchased_universals_kb import sold_universal_kb, confirm_del_universal_kb
from src.modules.profile.services.purchases_accounts import show_all_sold_account, show_sold_account, get_file_for_login, \
    check_sold_account, show_types_services_sold_account
from src.modules.profile.services.purchases_universals import show_sold_universal, show_all_sold_universal, \
    delete_sold_universal_han, check_universal_product, send_media_sold_universal
from src.services.database.categories.actions.products.universal.action_delete import delete_sold_universal
from src.services.database.categories.actions.products.universal.actions_get import get_sold_universal_by_universal_id
from src.services.products.accounts.tg.actions import check_account_validity, get_auth_codes
from src.services.database.categories.actions import get_sold_accounts_by_account_id, update_account_storage, \
    delete_sold_account, get_type_service_account, add_deleted_accounts
from src.services.database.categories.models import AccountStorage
from src.services.database.users.models import Users
from src.services.filesystem.account_actions import move_in_account, get_tdata_tg_acc, get_session_tg_acc
from src.services.secrets import decrypt_text, get_crypto_context, unwrap_dek
from src.utils.i18n import get_text
from src.utils.pars_number import e164_to_pretty

router = Router()


@router.callback_query(F.data.startswith("all_sold_universal:"))
async def all_sold_universal(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(':')[1])

    await show_all_sold_universal(
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
    )


@router.callback_query(F.data.startswith("sold_universal:"))
async def sold_universal(callback: CallbackQuery, user: Users):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id)
    if not universal:
        return

    await show_sold_universal(
        callback=callback,
        universal=universal,
        language=user.language,
        current_page=current_page,
    )


@router.callback_query(F.data.startswith("confirm_del_universal:"))
async def confirm_del_universal(callback: CallbackQuery, user: Users):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id)
    if not universal:
        return

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, 'profile_messages',
            "Confirm deletion of this product\n\n"
            "ID product: {sold_universal_id}\n"
            "Name: {name}"
        ).format(
            sold_universal_id=universal.sold_universal_id,
            name=universal.universal_storage.name,
        ),
        image_key='purchased_universal',
        reply_markup=confirm_del_universal_kb(
            language=user.language,
            sold_universal_id=universal.sold_universal_id,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("get_universal_media:"))
async def get_universal_media(callback: CallbackQuery, user: Users):
    sold_universal_id = int(callback.data.split(':')[1])

    universal = await check_universal_product(callback, user, sold_universal_id)
    if not universal:
        return

    await send_media_sold_universal(user.user_id, user.language, universal)


@router.callback_query(F.data.startswith("del_universal:"))
async def del_universal(callback: CallbackQuery, user: Users):
    sold_universal_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    universal = await check_universal_product(callback, user, sold_universal_id)
    if not universal:
        return

    await delete_sold_universal_han(
            callback=callback,
            user=user,
            universal=universal,
            current_page=current_page
        )
