from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.domain.crypto.decrypt import decrypt_text
from src.domain.crypto.key_ops import unwrap_dek
from src.models.create_models.accounts import CreateDeletedAccountDTO
from src.models.read_models import UsersDTO
from src.models.update_models import UpdateAccountStorageDTO
from src.modules.profile.keyboards import confirm_del_acc_kb, login_details_kb
from src.modules.profile.services.purchases_accounts import show_all_sold_account, show_sold_account, get_file_for_login, \
    check_sold_account, show_types_services_sold_account
from src.database.models.categories import AccountStorage, StorageStatus
from src.application.bot import Messages
from src.application.models.modules import ProfileModule
from src.infrastructure.translations import get_text
from src.utils.pars_number import e164_to_pretty

router = Router()


@router.callback_query(F.data == "services_sold_account")
async def services_sold_account(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    await show_types_services_sold_account(
        callback=callback, user=user, profile_module=profile_module, messages_service=messages_service
    )


@router.callback_query(F.data.startswith("all_sold_accounts:"))
async def all_sold_accounts(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    type_str = callback.data.split(':')[1]
    current_page = int(callback.data.split(':')[2])

    type_account_service = profile_module.account_moduls.storage_service.get_type_service_account(type_str)

    await show_all_sold_account(
        callback=callback,
        user=user,
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
        type_account_service=type_account_service,
        profile_module=profile_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("sold_account:"))
async def sold_account(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    sold_account_id = int(callback.data.split(':')[1])
    type_str = callback.data.split(':')[2]
    current_page = int(callback.data.split(':')[3])

    type_account_service = profile_module.account_moduls.storage_service.get_type_service_account(type_str)

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=user.language,
        current_page=current_page,
        type_account_service=type_account_service,
        profile_module=profile_module,
        messages_service=messages_service,
    )
    if not account:
        return

    await show_sold_account(
        callback=callback,
        user=user,
        account=account,
        language=user.language,
        current_page=current_page,
        type_account_service=type_account_service,
        profile_module = profile_module,
        messages_service = messages_service,
    )


@router.callback_query(F.data.startswith("login_details:"))
async def login_details(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    sold_account_id = int(callback.data.split(':')[1])
    type_str = callback.data.split(':')[2]
    current_page = int(callback.data.split(':')[3])

    type_account_service = profile_module.account_moduls.storage_service.get_type_service_account(type_str)

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=user.language,
        current_page=current_page,
        type_account_service=type_account_service,
        profile_module = profile_module,
        messages_service = messages_service,
    )
    if not account:
        return

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        event_message_key='purchased_accounts',
        reply_markup=login_details_kb(
            language=user.language,
            sold_account_id=account.sold_account_id,
            type_account_service=type_account_service,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("get_code_acc:"))
async def get_code_acc(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    sold_account_id = int(callback.data.split(':')[1])

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=user.language,
        profile_module = profile_module,
        messages_service = messages_service,
    )
    if not account:
        return

    message_search = await messages_service.send_msg.send(
        user.user_id, get_text(user.language, "profile_messages", 'search')
    )

    dt_and_code = await profile_module.get_auth_codes_use_case.get_auth_codes(account.account_storage)

    try:
        await message_search.delete()
    except Exception:
        pass

    if dt_and_code is False:
        await callback.answer(
            get_text(user.language, "profile_messages", "unable_to_retrieve_data"), show_alert=True
        )
        return

    dt_and_code = sorted(dt_and_code, key=lambda x: x[0])
    result_text = ''
    for i in range(len(dt_and_code)):
        if i > 5: # 5 последних кодов
            break
        date, code = dt_and_code[i]
        result_text += get_text(user.language, "profile_messages",
            "code_details"
        ).format(date=date.strftime(profile_module.conf.different.dt_format), code=code)

    if not result_text:
        await callback.answer(get_text(user.language, "profile_messages", "no_codes_found"), show_alert=True)
        return

    await messages_service.send_msg.send(user.user_id, message=result_text)


@router.callback_query(F.data.startswith("get_tdata_acc:"))
async def get_tdata_acc(callback: CallbackQuery, profile_module: ProfileModule, messages_service: Messages):
    await get_file_for_login(
        callback, profile_module.account_service.get_tdata_tg_acc, type_media='tdata_tg_id',
        profile_module=profile_module, messages_service=messages_service
    )


@router.callback_query(F.data.startswith("get_session_acc:"))
async def get_session_acc(callback: CallbackQuery, profile_module: ProfileModule, messages_service: Messages):
    await get_file_for_login(
        callback, profile_module.account_service.get_session_tg_acc, type_media='session_tg_id',
        profile_module=profile_module, messages_service=messages_service
    )


@router.callback_query(F.data.startswith("get_log_pas:"))
async def get_log_pas(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    sold_account_id = int(callback.data.split(':')[1])

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=user.language,
        profile_module=profile_module,
        messages_service=messages_service
    )
    if not account:
        return

    crypto = profile_module.crypto_provider.get()
    account_key = unwrap_dek(
        account.account_storage.encrypted_key,
        account.account_storage.encrypted_key_nonce,
        crypto.kek
    )

    await messages_service.send_msg.send(
        user.user_id,
        get_text(user.language, "profile_messages", "login_and_password_details").format(
            login=decrypt_text(account.account_storage.login_encrypted, account.account_storage.login_nonce, account_key),
            password=decrypt_text(account.account_storage.password_encrypted, account.account_storage.password_nonce, account_key)
        )
    )


@router.callback_query(F.data.startswith("chek_valid_acc:"))
async def chek_valid_acc(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    sold_account_id = int(callback.data.split(':')[1])
    type_str = callback.data.split(':')[2]
    current_page = int(callback.data.split(':')[3])
    current_validity = bool(int(callback.data.split(':')[4]))

    type_account_service = profile_module.account_moduls.storage_service.get_type_service_account(type_str)

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=user.language,
        current_page=current_page,
        type_account_service=type_account_service,
        profile_module=profile_module,
        messages_service=messages_service
    )
    if not account:
        return

    verification_message = await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(user.language, "profile_messages", "checking_for_validity")
    )

    result = await profile_module.validate_tg_account.check_account_validity(
        account_storage=account.account_storage,
        type_account_service=type_account_service,
        status=account.account_storage.status
    )

    try:
        await verification_message.delete()
    except Exception:
        pass

    if result:
        message = get_text(user.language, "profile_messages", 'account_is_valid')
    else:
        message = get_text(user.language, "profile_messages", 'account_is_not_valid')

    await callback.answer(message, show_alert=True)

    if result != current_validity: # если поменялась валидность аккаунта
        await profile_module.account_moduls.storage_service.update_account_storage(
            account_storage_id=account.account_storage.account_storage_id,
            data=UpdateAccountStorageDTO(is_valid=result),
        )
        account.account_storage.is_valid = result
        await show_sold_account(
            callback=callback,
            user=user,
            account=account,
            language=user.language,
            current_page=current_page,
            type_account_service=type_account_service,
            profile_module=profile_module,
            messages_service=messages_service
        )


@router.callback_query(F.data.startswith("confirm_del_acc:"))
async def confirm_del_acc(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    sold_account_id = int(callback.data.split(':')[1])
    type_str = callback.data.split(':')[2]
    current_page = int(callback.data.split(':')[3])

    type_account_service = profile_module.account_moduls.storage_service.get_type_service_account(type_str)

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=user.language,
        current_page=current_page,
        type_account_service=type_account_service,
        profile_module=profile_module,
        messages_service=messages_service
    )
    if not account:
        return

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "profile_messages",
            "confirmation_delete_account"
        ).format(
            phone_number=e164_to_pretty(account.account_storage.phone_number),
            name=account.name,
        ),
        event_message_key='purchased_accounts',
        reply_markup=confirm_del_acc_kb(
            language=user.language,
            sold_account_id=account.sold_account_id,
            type_account_service=type_account_service,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("del_account:"))
async def del_account(
    callback: CallbackQuery,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    sold_account_id = int(callback.data.split(':')[1])
    type_str = callback.data.split(':')[2]
    current_page = int(callback.data.split(':')[3])

    type_account_service = profile_module.account_moduls.storage_service.get_type_service_account(type_str)

    account = await check_sold_account(
        callback=callback,
        user=user,
        sold_account_id=sold_account_id,
        language=profile_module.conf.app.default_lang, # обязательно берём с таким языком, что бы в deleted_account записать с правильным значением
        current_page=current_page,
        type_account_service=type_account_service,
        profile_module=profile_module,
        messages_service=messages_service
    )
    if not account:
        return

    result = await profile_module.account_service.move_in_account(
        account=AccountStorage(**account.account_storage.model_dump()),
        type_service_name=type_account_service,
        status=StorageStatus.DELETED
    )
    if not result:
        await callback.answer(get_text(user.language, "miscellaneous", "an_error_occurred"), show_alert=True)
        return

    await profile_module.account_moduls.storage_service.update_account_storage(
        account_storage_id=account.account_storage.account_storage_id,
        data=UpdateAccountStorageDTO(
            status=StorageStatus.DELETED,
            is_active=False,
        )
    )
    await profile_module.account_moduls.sold_service.delete_sold_account(account.sold_account_id)
    await profile_module.account_moduls.deleted_service.create_deleted_account(
        data=CreateDeletedAccountDTO(
            account_storage_id=account.account_storage.account_storage_id,
            category_name=account.name,
            description=account.description
        )
    )

    await callback.answer(get_text(user.language, "profile_messages", "account_successfully_deleted"), show_alert=True)

    await show_all_sold_account(
        callback=callback,
        user=user,
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
        type_account_service=type_account_service,
        profile_module=profile_module,
        messages_service=messages_service
    )
