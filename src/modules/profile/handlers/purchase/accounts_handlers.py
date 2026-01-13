from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message, send_message
from src.config import get_config
from src.modules.profile.keyboard_profile import confirm_del_acc_kb, login_details_kb
from src.modules.profile.services.purchases import show_all_sold_account, show_sold_account, get_file_for_login, \
    check_sold_account, show_types_services_sold_account
from src.services.accounts.tg.actions import check_account_validity, get_auth_codes
from src.services.database.categories.actions import get_sold_accounts_by_account_id, update_account_storage, \
    delete_sold_account, get_type_service_account, add_deleted_accounts
from src.services.database.categories.models import AccountStorage
from src.services.database.users.models import Users
from src.services.filesystem.account_actions import move_in_account, get_tdata_tg_acc, get_session_tg_acc
from src.services.secrets import decrypt_text, get_crypto_context, unwrap_dek
from src.utils.i18n import get_text
from src.utils.pars_number import e164_to_pretty

router = Router()


@router.callback_query(F.data == "services_sold_account")
async def services_sold_account(callback: CallbackQuery, user: Users):
    await show_types_services_sold_account(callback=callback, user=user)


@router.callback_query(F.data.startswith("all_sold_accounts:"))
async def all_sold_accounts(callback: CallbackQuery, user: Users):
    type_account_service = get_type_service_account(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    await show_all_sold_account(
        callback=callback,
        user=user,
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
        type_account_service=type_account_service
    )


@router.callback_query(F.data.startswith("sold_account:"))
async def sold_account(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service = get_type_service_account(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])

    account = await get_sold_accounts_by_account_id(sold_account_id, language=user.language)
    if not account:
        await callback.answer(get_text(user.language, 'profile_messages', "Account not found"))
        return

    await show_sold_account(
        callback=callback,
        user=user,
        account=account,
        language=user.language,
        current_page=current_page,
        type_account_service=type_account_service
    )


@router.callback_query(F.data.startswith("login_details:"))
async def login_details(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service = get_type_service_account(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])

    account = await get_sold_accounts_by_account_id(sold_account_id, language=user.language)
    if not account:
        await callback.answer(get_text(user.language, 'profile_messages', "Account not found"))
        return

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='purchased_accounts',
        reply_markup=await login_details_kb(
            language=user.language,
            sold_account_id=account.sold_account_id,
            type_account_service=type_account_service,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("get_code_acc:"))
async def get_code_acc(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])

    account = await get_sold_accounts_by_account_id(sold_account_id, language=user.language)
    if not account:
        await callback.answer(get_text(user.language, 'profile_messages', "Account not found"))
        return

    message_search = await send_message(user.user_id, get_text(user.language, 'profile_messages', 'Search...'))

    dt_and_code = await get_auth_codes(AccountStorage(**account.account_storage.model_dump()))

    try:
        await message_search.delete()
    except Exception:
        pass

    if dt_and_code is False:
        await callback.answer(get_text(user.language, 'profile_messages', "Unable to retrieve data"), show_alert=True)
        return

    dt_and_code = sorted(dt_and_code, key=lambda x: x[0])
    result_text = ''
    for i in range(len(dt_and_code)):
        if i > 5: # 5 последних кодов
            break
        date, code = dt_and_code[i]
        result_text += get_text(user.language, 'profile_messages',
            "Date: {date} \nCode: <code>{code}</code>\n\n"
        ).format(date=date.strftime(get_config().different.dt_format), code=code)

    if not result_text:
        await callback.answer(get_text(user.language, 'profile_messages', "No codes found"), show_alert=True)
        return

    await send_message(user.user_id, message=result_text)


@router.callback_query(F.data.startswith("get_tdata_acc:"))
async def get_tdata_acc(callback: CallbackQuery):
    await get_file_for_login(callback, get_tdata_tg_acc, type_media='tdata_tg_id')


@router.callback_query(F.data.startswith("get_session_acc:"))
async def get_session_acc(callback: CallbackQuery):
    await get_file_for_login(callback, get_session_tg_acc, type_media='session_tg_id')


@router.callback_query(F.data.startswith("get_log_pas:"))
async def get_log_pas(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])

    account = await get_sold_accounts_by_account_id(sold_account_id, language=user.language)
    if not account:
        await callback.answer(get_text(user.language, 'profile_messages', "Account not found"))
        return

    crypto = get_crypto_context()
    account_key = unwrap_dek(
        account.account_storage.encrypted_key,
        crypto.nonce_b64_dek,
        crypto.kek
    )

    await send_message(
        user.user_id,
        get_text(user.language, 'profile_messages', "Login: <code>{login}</code> \nPassword: <code>{password}</code>").format(
            login=decrypt_text(account.account_storage.login_encrypted, account.account_storage.login_nonce, account_key),
            password=decrypt_text(account.account_storage.password_encrypted, account.account_storage.password_nonce, account_key)
        )
    )


@router.callback_query(F.data.startswith("chek_valid_acc:"))
async def chek_valid_acc(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service = get_type_service_account(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])
    current_validity = bool(int(callback.data.split(':')[4]))

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=user.language,
        current_page=current_page,
        type_account_service=type_account_service
    )
    if not account:
        return

    verification_message = await send_message(chat_id=user.user_id,message=get_text(user.language, 'profile_messages', "Checking for validity..."))

    result = await check_account_validity(
        account_storage=AccountStorage(**account.account_storage.model_dump()),
        type_account_service=type_account_service
    )

    try:
        await verification_message.delete()
    except Exception:
        pass

    if result:
        message = get_text(user.language, 'profile_messages', 'The account is valid')
    else:
        message = get_text(user.language, 'profile_messages', 'The account is not valid')

    await callback.answer(message, show_alert=True)

    if result != current_validity: # если поменялась валидность аккаунта
        await update_account_storage(account_storage_id=account.account_storage.account_storage_id, is_valid=result)
        account.account_storage.is_valid = result
        await show_sold_account(
            callback=callback,
            user=user,
            account=account,
            language=user.language,
            current_page=current_page,
            type_account_service=type_account_service
        )


@router.callback_query(F.data.startswith("confirm_del_acc:"))
async def confirm_del_acc(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service = get_type_service_account(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=user.language,
        current_page=current_page,
        type_account_service=type_account_service
    )
    if not account:
        return

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, 'profile_messages',
            "Confirm deletion of this account?\n\n"
            "Phone number: {phone_number}\n"
            "Name: {name}"
        ).format(
            phone_number=e164_to_pretty(account.account_storage.phone_number),
            name=account.name,
        ),
        image_key='purchased_accounts',
        reply_markup=confirm_del_acc_kb(
            language=user.language,
            sold_account_id=account.sold_account_id,
            type_account_service=type_account_service,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("del_account:"))
async def del_account(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service = get_type_service_account(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=get_config().app.default_lang, # обязательно берём с таким языком, что бы в deleted_account записать с правильным значением
        current_page=current_page,
        type_account_service=type_account_service
    )
    if not account:
        return


    result = await move_in_account(account=AccountStorage(**account.account_storage.model_dump()), type_service_name=type_account_service, status='deleted')
    if not result:
        await callback.answer(get_text(user.language, 'profile_messages', "An error occurred, please try again"), show_alert=True)
        return

    await update_account_storage(
        account_storage_id=account.account_storage.account_storage_id,
        status='deleted',
        is_active=False
    )
    await delete_sold_account(account.sold_account_id)
    await add_deleted_accounts(
        type_account_service=type_account_service,
        account_storage_id=account.account_storage.account_storage_id,
        category_name=account.name,
        description=account.description
    )

    await callback.answer(get_text(user.language, 'profile_messages', "The account has been successfully deleted"), show_alert=True)

    await show_all_sold_account(
        callback=callback,
        user=user,
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
        type_account_service=type_account_service
    )
