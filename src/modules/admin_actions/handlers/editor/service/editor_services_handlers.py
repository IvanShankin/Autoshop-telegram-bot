import asyncio

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.exceptions.service_exceptions import ServiceTypeBusy, ServiceContainsCategories
from src.modules.admin_actions.services import show_service
from src.modules.admin_actions.keyboards import all_services_account_admin_kb, all_services_types_kb, \
    to_services_kb,  back_in_service_kb, delete_service_kb
from src.modules.admin_actions.schemas.editor_categories import GetServiceNameData, RenameServiceData
from src.modules.admin_actions.state.editor_categories import GetServiceName, RenameService
from src.services.database.selling_accounts.actions import add_account_services, update_account_service, \
    delete_account_service
from src.services.database.users.models import Users
from src.utils.core_logger import logger
from src.utils.i18n import  get_text

router = Router()


@router.callback_query(F.data == "services_editor")
async def show_catalog_services_accounts(callback: CallbackQuery, user: Users):
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='admin_panel',
        reply_markup=await all_services_account_admin_kb(user.language)
    )


@router.callback_query(F.data == "add_account_service")
async def add_account_service(callback: CallbackQuery, user: Users):
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor","Select service_acc type"),
        reply_markup=await all_services_types_kb(user.language)
    )


@router.callback_query(F.data.startswith("select_type_service:"))
async def select_type_service(callback: CallbackQuery, state: FSMContext, user: Users):
    service_type_id = int(callback.data.split(':')[1])
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor",'Enter a name for the new service_acc')
    )
    await state.set_state(GetServiceName.service_name)
    await state.update_data(
        service_type_id=service_type_id,
    )


@router.message(GetServiceName.service_name)
async def get_service_name(message: Message, state: FSMContext, user: Users):
    data = GetServiceNameData(** await state.get_data())
    try:
        await add_account_services(message.text, data.service_type_id)
    except ServiceTypeBusy:
        await send_message(user.user_id, get_text(user.language, "admins_editor","Unable to create. This service_acc type is in use"))
        return

    await send_message(user.user_id, get_text(user.language, "admins_editor","Service successfully created"), reply_markup=to_services_kb(user.language))


@router.callback_query(F.data.startswith("show_service_acc_admin:"))
async def show_service_acc_admin(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    service_id = int(callback.data.split(':')[1])
    await show_service(user=user, callback=callback, message_id=callback.message.message_id, service_id=service_id)


@router.callback_query(F.data.startswith("service_update_index:"))
async def service_update_index(callback: CallbackQuery, user: Users):
    service_id = int(callback.data.split(':')[1])
    new_index = int(callback.data.split(':')[2])

    if new_index >= 0:
        await update_account_service(service_id, index=new_index)
    await callback.answer(get_text(user.language, "admins_editor","Successfully updated"))
    await show_service(user=user, callback=callback, message_id=callback.message.message_id, service_id=service_id)


@router.callback_query(F.data.startswith("service_update_show:"))
async def service_update_show(callback: CallbackQuery, user: Users):
    service_id = int(callback.data.split(':')[1])
    show = bool(int(callback.data.split(':')[2]))

    await update_account_service(service_id, show=show)
    await callback.answer(get_text(user.language, "admins_editor","Successfully updated"))
    await show_service(user=user, callback=callback, message_id=callback.message.message_id, service_id=service_id)


@router.callback_query(F.data.startswith("service_rename:"))
async def service_rename(callback: CallbackQuery, state: FSMContext, user: Users):
    service_id = int(callback.data.split(':')[1])

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "admins_editor","Please enter a new name"),
        reply_markup=back_in_service_kb(user.language, service_id)
    )

    await state.update_data(service_id=service_id)
    await state.set_state(RenameService.service_name)


@router.message(RenameService.service_name)
async def update_service_name(message: Message, state: FSMContext, user: Users):
    data = RenameServiceData(**await state.get_data())

    try:
        await message.delete()
    except Exception:
        pass

    try:
        await update_account_service(data.service_id, name=message.text)

        await show_service(user=user, service_id=data.service_id, send_new_message=True)
        info_message = await send_message(user.user_id, get_text(user.language, "admins_editor","Name changed successfully"))
        await asyncio.sleep(3)
        try:
            await info_message.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"[update_service_name] handler Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("service_confirm_delete:"))
async def service_confirm_delete(callback: CallbackQuery, user: Users):
    service_id = int(callback.data.split(':')[1])

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor",
            "Are you sure you want to delete this service_acc? \n\n"
            "Before deleting, make sure that this service_acc does not contain categories!"
        ),
        reply_markup=delete_service_kb(user.language, service_id)
    )


@router.callback_query(F.data.startswith("delete_acc_service:"))
async def delete_acc_service(callback: CallbackQuery, user: Users):
    service_id = int(callback.data.split(':')[1])

    try:
        await delete_account_service(service_id)
        message = get_text(user.language, "admins_editor","Service successfully removed!")
        reply_markup = to_services_kb(user.language)
    except ServiceContainsCategories:
        message = get_text(user.language, "admins_editor","The service_acc has categories, delete them first")
        reply_markup = back_in_service_kb(user.language, service_id)

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=reply_markup
    )