from typing import Any, Literal, Optional

from aiogram.types import CallbackQuery, FSInputFile

from src.bot_actions.bot_instance import get_bot
from src.bot_actions.messages import edit_message, send_message
from src.config import get_config
from src.exceptions.business import ForbiddenError
from src.modules.profile.keyboards import sold_accounts_kb, account_kb, sold_account_type_service_kb
from src.services.database.admins.actions import check_admin
from src.services.database.categories.actions import get_sold_accounts_by_account_id, get_tg_account_media, \
    update_tg_account_media
from src.services.database.categories.models import SoldAccountFull, AccountStorage, AccountServiceType
from src.services.database.users.actions import get_user
from src.services.database.users.models import Users
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text
from src.utils.pars_number import e164_to_pretty


async def show_types_services_sold_account(
    user: Users,
    callback: CallbackQuery,
):
    """Отредактирует сообщение и покажет сервисы купленных аккаунтов, в которых пользователь приобрёл аккаунт"""
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "profile_messages", "select_account_type"),
        image_key="purchases",
        reply_markup=await sold_account_type_service_kb(user.language, user.user_id)
    )


async def show_all_sold_account(
    callback: CallbackQuery,
    user: Users,
    user_id: int,
    language: str,
    message_id: int,
    current_page: int,
    type_account_service: AccountServiceType | None
):
    """Отредактирует сообщение и покажет необходимое для аккаунтов по всем сервисам"""
    result_type_service = await check_type_account_service(
        callback=callback, user=user, language=language, type_account_service=type_account_service
    )
    if not result_type_service:
        return

    await edit_message(
        chat_id=user_id,
        message_id=message_id,
        image_key='purchased_accounts',
        reply_markup=await sold_accounts_kb(
            language=language,
            current_page=current_page,
            type_account_service=type_account_service,
            user_id=user_id
        )
    )


async def show_sold_account(
    callback: CallbackQuery,
    user: Users,
    account: SoldAccountFull,
    language: str,
    current_page: int,
    type_account_service: AccountServiceType | None
):
    """Отредактирует сообщение и покажет необходимое для аккаунта"""
    result_type_service = await check_type_account_service(
        callback=callback, user=user, language=language, type_account_service=type_account_service
    )
    if not result_type_service:
        return

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(
            language,
            "profile_messages",
            "account_details"
        ).format(
            product_id=account.sold_account_id,
            phone_number=e164_to_pretty(account.account_storage.phone_number),
            name=account.name,
            description=(
                account.description
                if account.description else
                get_text(language, "miscellaneous", "no")
            ),
            valid=(
                get_text(language, "profile_messages","valid")
                if account.account_storage.is_valid
                else get_text(language, "profile_messages","not_valid")
            ),
            sold_at=account.sold_at.strftime(get_config().different.dt_format),
        ),
        image_key='purchased_accounts',
        reply_markup=account_kb(
            language=language,
            sold_account_id=account.sold_account_id,
            current_page=current_page,
            type_account_service=type_account_service,
            current_validity=account.account_storage.is_valid
        )
    )


async def check_sold_account(
    callback: CallbackQuery,
    user: Users,
    sold_account_id: int,
    language: str,
    current_page: Optional[int] = None,
    type_account_service: Optional[AccountServiceType] = None
) -> SoldAccountFull | None:
    """
    Проверит наличие аккаунта, если нет, то выведет соответствующие сообщение и вернёт к выбору аккаунта.
    Проверит что данный товар принадлежит пользователю, если нет, то вызовет ошибку
    """
    account = await get_sold_accounts_by_account_id(sold_account_id, language=language)
    if not account:
        await callback.answer(get_text(language, "profile_messages", "account_not_found"), show_alert=True)
        if current_page and type_account_service:
            await show_all_sold_account(
                callback=callback,
                user=user,
                user_id=callback.from_user.id,
                language=language,
                message_id=callback.message.message_id,
                current_page=current_page,
                type_account_service=type_account_service
            )
        return None

    if account.owner_id != user.user_id and not await check_admin(user.user_id):
        raise ForbiddenError()

    if type_account_service:
        result_check_service = await check_type_account_service(
            callback=callback, user=user, language=language, type_account_service=type_account_service
        )
        if not result_check_service:
            return None

    return account


async def check_type_account_service(
    callback: CallbackQuery,
    user: Users,
    language: str,
    type_account_service: AccountServiceType | None
) -> bool:
    if type_account_service is None:
        await callback.answer(get_text(language, "profile_messages", "service_not_found"), show_alert=True)
        await show_types_services_sold_account(user=user, callback=callback, )
        return False

    return True


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
        await callback.answer(get_text(user.language, "profile_messages", "account_not_found"))
        return

    if account.owner_id != user.user_id and not await check_admin(user.user_id):
        raise ForbiddenError()

    tg_media = await get_tg_account_media(account.account_storage.account_storage_id)
    if tg_media and getattr(tg_media, type_media):
        bot = await get_bot()
        try:
            await bot.send_document(chat_id=user.user_id, document=getattr(tg_media, type_media))
            return
        except Exception:
            # устарел или недействителен
            logger = get_logger(__name__)
            logger.warning(f"[get_file_for_login] {type_media} недействителен, он будет удалён")
            await update_tg_account_media(tg_media.tg_account_media_id, **{type_media: None}) # обнуляем затронутое поле

    message_load = await send_message(user.user_id, get_text(user.language, "profile_messages", "loading"))

    async for path in func_get_file(AccountStorage(**account.account_storage.model_dump())):
        if path:
            archive = FSInputFile(path)
            bot = await get_bot()
            message = await bot.send_document(chat_id=user.user_id, document=archive)
            await update_tg_account_media(tg_media.tg_account_media_id, **{type_media: message.document.file_id})
        else:
            await callback.answer(get_text(user.language, "profile_messages", "unable_to_retrieve_data"), show_alert=True)

    try:
        await message_load.delete()
    except Exception:
        pass