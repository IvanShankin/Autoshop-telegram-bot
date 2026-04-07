from typing import Any, Literal, Optional

from aiogram.types import CallbackQuery

from src.models.update_models import UpdateTgAccountMediaDTO
from src.modules.profile.keyboards import sold_accounts_kb, account_kb, sold_account_type_service_kb
from src.database.models.categories import AccountStorage, AccountServiceType
from src.models.read_models import SoldAccountFull, UsersDTO
from src.services.bot import Messages
from src.services.models.modules import ProfileModule
from src.utils.i18n import get_text
from src.utils.pars_number import e164_to_pretty


async def show_types_services_sold_account(
    user: UsersDTO,
    callback: CallbackQuery,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    """Отредактирует сообщение и покажет сервисы купленных аккаунтов, в которых пользователь приобрёл аккаунт"""
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "profile_messages", "select_account_type"),
        event_message_key="purchases",
        reply_markup=await sold_account_type_service_kb(user.language, user.user_id, profile_module)
    )


async def show_all_sold_account(
    callback: CallbackQuery,
    user: UsersDTO,
    user_id: int,
    language: str,
    message_id: int,
    current_page: int,
    type_account_service: AccountServiceType | None,
    profile_module: ProfileModule,
    messages_service: Messages,
):
    """Отредактирует сообщение и покажет необходимое для аккаунтов по всем сервисам"""
    result_type_service = await check_type_account_service(
        callback=callback, user=user, language=language, type_account_service=type_account_service,
        profile_module=profile_module, messages_service=messages_service
    )
    if not result_type_service:
        return

    await messages_service.edit_msg.edit(
        chat_id=user_id,
        message_id=message_id,
        event_message_key='purchased_accounts',
        reply_markup=await sold_accounts_kb(
            language=language,
            current_page=current_page,
            type_account_service=type_account_service,
            user_id=user_id,
            profile_module=profile_module,
        )
    )


async def show_sold_account(
    callback: CallbackQuery,
    user: UsersDTO,
    account: SoldAccountFull,
    language: str,
    current_page: int,
    type_account_service: AccountServiceType | None,
    messages_service: Messages,
    profile_module: ProfileModule,
):
    """Отредактирует сообщение и покажет необходимое для аккаунта"""
    result_type_service = await check_type_account_service(
        callback=callback, user=user, language=language, type_account_service=type_account_service,
        profile_module=profile_module, messages_service=messages_service
    )
    if not result_type_service:
        return

    await messages_service.edit_msg.edit(
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
            sold_at=account.sold_at.strftime(profile_module.conf.different.dt_format),
        ),
        event_message_key='purchased_accounts',
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
    user: UsersDTO,
    sold_account_id: int,
    language: str,
    messages_service: Messages,
    profile_module: ProfileModule,
    current_page: Optional[int] = None,
    type_account_service: Optional[AccountServiceType] = None,
) -> SoldAccountFull | None:
    """
    Проверит наличие аккаунта, если нет, то выведет соответствующие сообщение и вернёт к выбору аккаунта.
    Проверит что данный товар принадлежит пользователю, если нет, то вызовет ошибку
    """
    account = await profile_module.account_moduls.sold_service.get_sold_account_by_account_id(
        sold_account_id=sold_account_id, language=language
    )
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
                type_account_service=type_account_service,
                messages_service=messages_service,
                profile_module=profile_module,
            )
        return None

    await profile_module.permission_service.check_permission(
        current_user_id=user.user_id, target_user_id=account.owner_id
    )

    if type_account_service:
        result_check_service = await check_type_account_service(
            callback=callback, user=user, language=language, type_account_service=type_account_service,
            profile_module=profile_module, messages_service=messages_service
        )
        if not result_check_service:
            return None

    return account


async def check_type_account_service(
    callback: CallbackQuery,
    user: UsersDTO,
    language: str,
    type_account_service: AccountServiceType | None,
    profile_module: ProfileModule,
    messages_service: Messages,
) -> bool:
    if type_account_service is None:
        await callback.answer(get_text(language, "profile_messages", "service_not_found"), show_alert=True)
        await show_types_services_sold_account(
            user=user, callback=callback, profile_module=profile_module, messages_service=messages_service
        )
        return False

    return True


async def get_file_for_login(
    callback: CallbackQuery,
    func_get_file: Any,
    type_media:  Literal["tdata_tg_id", "session_tg_id"],
    profile_module: ProfileModule,
    messages_service: Messages,
):
    """
    :param func_get_file: функция для получения пути к файлу
    :param type_media: тип чего отправляем.
    :return:
    """
    sold_account_id = int(callback.data.split(':')[1])
    user = await profile_module.user_service.get_user(callback.from_user.id)

    account = await profile_module.account_moduls.sold_service.get_sold_account_by_account_id(
        sold_account_id, language=user.language
    )
    if not account:
        await callback.answer(get_text(user.language, "profile_messages", "account_not_found"))
        return

    await profile_module.permission_service.check_permission(
        current_user_id=user.user_id, target_user_id=account.owner_id
    )

    tg_media = await profile_module.account_moduls.tg_media_service.get_tg_account_media(
        account.account_storage.account_storage_id
    )
    if tg_media and getattr(tg_media, type_media):
        try:
            await messages_service.send_file.send_document(chat_id=user.user_id, file_id=getattr(tg_media, type_media))
            return
        except Exception:
            # устарел или недействителен
            profile_module.logger.warning(f"[get_file_for_login] {type_media} недействителен, он будет удалён")

            await profile_module.account_moduls.tg_media_service.update_tg_account_media(
                tg_media.tg_account_media_id,
                data=UpdateTgAccountMediaDTO(
                    **{type_media: None}
                )
            ) # обнуляем затронутое поле

    message_load = await messages_service.send_msg.send(
        user.user_id, get_text(user.language, "profile_messages", "loading")
    )

    async for path in func_get_file(AccountStorage(**account.account_storage.model_dump())):
        if path:
            message = await messages_service.send_file.send_document(chat_id=user.user_id, file_path=path)
            await profile_module.account_moduls.tg_media_service.update_tg_account_media(
                tg_media.tg_account_media_id,
                data=UpdateTgAccountMediaDTO(
                    **{type_media: message.document.file_id}
                )
            )  # обнуляем затронутое поле
        else:
            await callback.answer(
                get_text(user.language, "profile_messages", "unable_to_retrieve_data"),
                show_alert=True
            )

    try:
        await message_load.delete()
    except Exception:
        pass