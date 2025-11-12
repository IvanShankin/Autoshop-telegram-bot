from typing import Any, Literal

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

from src.bot_actions.actions import edit_message, send_message
from src.bot_actions.bot_instance import get_bot
from src.config import DT_FORMAT, DEFAULT_LANG
from src.modules.profile.keyboard_profile import services_sold_accounts_kb, sold_accounts_kb, account_kb, \
    confirm_del_acc_kb, login_details_kb
from src.services.database.selling_accounts.actions import get_sold_accounts_by_account_id, update_account_storage, \
    delete_sold_account, get_type_account_service, add_deleted_accounts, get_tg_account_media, update_tg_account_media
from src.services.database.selling_accounts.models import SoldAccountFull, AccountStorage
from src.services.database.users.actions import get_user
from src.services.database.users.models import Users
from src.services.filesystem.account_actions import move_in_account, check_account_validity, get_tdata_tg_acc, \
    get_session_tg_acc, get_auth_codes
from src.utils.core_logger import logger
from src.utils.i18n import get_text
from src.utils.secret_data import decrypt_data

router = Router()

async def show_all_sold_account(user_id: int, language: str, message_id: int, current_page: int, type_account_service_id: int):
    """Отредактирует сообщение и покажет необходимое для аккаунтов по всем сервисам"""
    await edit_message(
        chat_id=user_id,
        message_id=message_id,
        image_key='purchased_accounts',
        reply_markup=await sold_accounts_kb(
            language=language,
            current_page=current_page,
            type_account_service_id=type_account_service_id,
            user_id=user_id
        )
    )

async def show_sold_account(
    callback: CallbackQuery,
    account:  SoldAccountFull,
    language: str,
    current_page: int,
    type_account_service_id: int
):
    """Отредактирует сообщение и покажет необходимое для аккаунта"""
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(
            language,
            'profile_messages',
            "Phone: {phone_number}\n\n"
            "Name: {name}\n"
            "Description: {description}\n\n"
            "{valid}\n"
            "Purchased: {sold_at}"
        ).format(
            phone_number=account.account_storage.phone_number,
            name=account.name,
            description=account.description,
            valid=(
                get_text(language, 'profile_messages',"Valid")
                if account.account_storage.is_valid
                else get_text(language, 'profile_messages',"Not valid")
            ),
            sold_at=account.sold_at.strftime(DT_FORMAT),
        ),
        image_key='purchased_accounts',
        reply_markup=account_kb(
            language=language,
            sold_account_id=account.sold_account_id,
            current_page=current_page,
            type_account_service_id=type_account_service_id,
            current_validity=account.account_storage.is_valid
        )
    )

async def cheek_sold_account(
    callback: CallbackQuery,
    sold_account_id: int,
    language: str,
    current_page: int,
    type_account_service_id: int
) -> SoldAccountFull | None:
    """Проверит наличие аккаунта, если нет, то выведет соответствующие сообщение и вернёт к выбору аккаунта"""
    account = await get_sold_accounts_by_account_id(sold_account_id, language=language)
    if not account:
        await callback.answer(get_text(user.language, 'profile_messages', "Account not found"), show_alert=True)
        await show_all_sold_account(
            user_id=callback.from_user.id,
            language=language,
            message_id=callback.message.message_id,
            current_page=current_page,
            type_account_service_id=type_account_service_id
        )

    return account

async def get_file_for_login(callback: CallbackQuery, func_get_file: Any, type_media:  Literal["tdata_tg_id", "session_tg_id"]):
    """
    :param func_get_file: функция для получения пути к файлу
    :param type_media: тип чего отправляем.
    :return:
    """
    sold_account_id = int(callback.data.split(':')[1])
    user = await get_user(callback.from_user.id)

    account = await get_sold_accounts_by_account_id(sold_account_id, language=user.language)
    if not account:
        await callback.answer(get_text(user.language, 'profile_messages', "Account not found"))
        return

    tg_media = await get_tg_account_media(account.account_storage.account_storage_id)
    if tg_media and getattr(tg_media, type_media):
        bot = await get_bot()
        try:
            await bot.send_document(chat_id=user.user_id, document=getattr(tg_media, type_media))
            return
        except Exception:
            # устарел или недействителен
            logger.warning(f"[get_file_for_login] {type_media} недействителен, он будет удалён")
            await update_tg_account_media(tg_media.tg_account_media_id, **{type_media: None}) # обнуляем затронутое поле

    message_load = await send_message(user.user_id, get_text(user.language, 'profile_messages', "Loading..."))

    async for path in func_get_file(AccountStorage(**account.account_storage.model_dump())):
        if path:
            archive = FSInputFile(path)
            bot = await get_bot()
            message = await bot.send_document(chat_id=user.user_id, document=archive)
            await update_tg_account_media(tg_media.tg_account_media_id, **{type_media: message.document.file_id})
        else:
            await callback.answer(get_text(user.language, 'profile_messages', "Unable to retrieve data"), show_alert=True)

    try:
        await message_load.delete()
    except Exception:
        pass


@router.callback_query(F.data == "all_sold_accounts_none")
async def list_is_over(callback: CallbackQuery):
    await callback.answer("Список закончился")


@router.callback_query(F.data == "services_sold_accounts")
async def services_sold_accounts(callback: CallbackQuery, user: Users):
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='purchased_accounts',
        reply_markup=await services_sold_accounts_kb(user.language, user.user_id)
    )


@router.callback_query(F.data.startswith("all_sold_accounts:"))
async def all_sold_accounts(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(':')[1])
    type_account_service_id = int(callback.data.split(':')[2])

    await show_all_sold_account(
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
        type_account_service_id=type_account_service_id
    )


@router.callback_query(F.data.startswith("sold_account:"))
async def sold_account(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service_id = int(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])

    account = await get_sold_accounts_by_account_id(sold_account_id, language=user.language)
    if not account:
        await callback.answer(get_text(user.language, 'profile_messages', "Account not found"))
        return

    await show_sold_account(
        callback=callback,
        account=account,
        language=user.language,
        current_page=current_page,
        type_account_service_id=type_account_service_id
    )

@router.callback_query(F.data.startswith("login_details:"))
async def login_details(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service_id = int(callback.data.split(':')[2])
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
            type_account_service_id=type_account_service_id,
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
        ).format(date=date.strftime(DT_FORMAT), code=code)

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

    await send_message(
        user.user_id,
        get_text(user.language, 'profile_messages', "Login: <code>{login}</code> \nPassword: <code>{password}</code>").format(
            login=decrypt_data(account.account_storage.login_encrypted),
            password=decrypt_data(account.account_storage.password_encrypted)
        )
    )


@router.callback_query(F.data.startswith("chek_valid_acc:"))
async def chek_valid_acc(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service_id = int(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])
    current_validity = bool(int(callback.data.split(':')[4]))

    account = await cheek_sold_account(
        callback=callback,
        sold_account_id=sold_account_id,
        language=user.language,
        current_page=current_page,
        type_account_service_id=type_account_service_id
    )
    if not account:
        return

    type_service = await get_type_account_service(type_account_service_id)

    verification_message = await send_message(chat_id=user.user_id,message=get_text(user.language, 'profile_messages', "Checking for validity..."))

    result = await check_account_validity(
        account_storage=AccountStorage(**account.account_storage.model_dump()),
        type_service_name=type_service.name
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
            account=account,
            language=user.language,
            current_page=current_page,
            type_account_service_id=type_account_service_id
        )


@router.callback_query(F.data.startswith("confirm_del_acc:"))
async def confirm_del_acc(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service_id = int(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])

    account = await cheek_sold_account(
        callback=callback,
        sold_account_id=sold_account_id,
        language=user.language,
        current_page=current_page,
        type_account_service_id=type_account_service_id
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
            phone_number=account.account_storage.phone_number,
            name=account.name,
        ),
        image_key='purchased_accounts',
        reply_markup=confirm_del_acc_kb(
            language=user.language,
            sold_account_id=account.sold_account_id,
            type_account_service_id=type_account_service_id,
            current_page=current_page,
        )
    )


@router.callback_query(F.data.startswith("del_account:"))
async def del_account(callback: CallbackQuery, user: Users):
    sold_account_id = int(callback.data.split(':')[1])
    type_account_service_id = int(callback.data.split(':')[2])
    current_page = int(callback.data.split(':')[3])

    account = await cheek_sold_account(
        callback=callback,
        sold_account_id=sold_account_id,
        language=DEFAULT_LANG, # обязательно берём с таким языком, что бы в deleted_account записать с правильным значением
        current_page=current_page,
        type_account_service_id=type_account_service_id
    )
    if not account:
        return

    type_service = await get_type_account_service(type_account_service_id)

    result = await move_in_account(account=AccountStorage(**account.account_storage.model_dump()), type_service_name=type_service.name, status='deleted')
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
        type_account_service_id=type_account_service_id,
        account_storage_id=account.account_storage.account_storage_id,
        category_name=account.name,
        description=account.description
    )

    await callback.answer(get_text(user.language, 'profile_messages', "The account has been successfully deleted"), show_alert=True)

    await show_all_sold_account(
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
        type_account_service_id=type_account_service_id
    )
