from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.models.update_models import UpdateStickerDTO
from src.modules.admin_actions.keyboards.editors.event_message_kb import sticker_editor_kb, back_in_sticker_editor
from src.modules.admin_actions.schemas import UpdateEventMsgData
from src.modules.admin_actions.state.editors.editor_event_msg import UpdateEventMsg

from src.infrastructure.translations import get_text


router = Router()


async def show_sticker_editor(
    event_msg_key: str,
    current_page: int,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    new_message: bool = False,
    callback: CallbackQuery = None
):
    sticker = await admin_module.stickers_service.get_sticker(event_msg_key)

    message = get_text(
        user.language, "admins_editor_event_msg", "where_used_and_indicate_show"
    ).format(
        where=get_text(user.language, "event_msg_description", event_msg_key),
        show=sticker.show if sticker else get_text(user.language, "miscellaneous", "no"),
        current=" " if sticker and sticker.file_id else get_text(user.language, "miscellaneous", "no")
    )

    reply_markup = sticker_editor_kb(user.language, event_msg_key, current_show=sticker.show,current_page=current_page)

    if new_message:
        await messages_service.send_msg.send(chat_id=user.user_id, message=message, reply_markup=await reply_markup)
    else:
        await messages_service.edit_msg.edit(
            chat_id=user.user_id,
            message_id=callback.message.message_id,
            message=message,
            event_message_key="admin_panel",
            reply_markup=await reply_markup
        )


@router.callback_query(F.data.startswith("edit_sticker:"))
async def edit_sticker(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    event_msg_key = str(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    await show_sticker_editor(
        event_msg_key=event_msg_key,
        current_page=current_page,
        user=user,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("sticker_update_show:"))
async def sticker_update_show(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    event_msg_key = callback.data.split(':')[1]
    new_show = bool(int(callback.data.split(':')[2]))
    current_page = int(callback.data.split(':')[3])

    await admin_module.stickers_service.update_sticker(
        key=event_msg_key,
        data=UpdateStickerDTO(show=new_show),
        make_commit=True,
        filling_redis=True,
    )
    await callback.answer(get_text(user.language, "miscellaneous", "successfully_updated"), show_alert=True)

    await show_sticker_editor(
        event_msg_key=event_msg_key,
        current_page=current_page,
        user=user,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("show_current_sticker:"))
async def show_current_sticker(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    event_msg_key = callback.data.split(':')[1]
    sticker = await admin_module.stickers_service.get_sticker(event_msg_key)

    if sticker and sticker.file_id:
        await messages_service.sticker_sender.send(chat_id=user.user_id, key=event_msg_key)
        return

    await callback.answer(
        text=get_text(user.language, "admins_editor_event_msg", "sticker_not_found"),
        show_alert=True
    )


@router.callback_query(F.data.startswith("change_sticker:"))
async def change_sticker(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    event_msg_key = str(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_event_msg",
            "get_new_sticker"
        ),
        reply_markup=await back_in_sticker_editor(user.language, event_msg_key, current_page)
    )
    await state.update_data(event_message_key=event_msg_key, current_page=current_page)
    await state.set_state(UpdateEventMsg.get_new_sticker)


@router.message(UpdateEventMsg.get_new_sticker, F.sticker)
async def change_sticker_result(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    data = UpdateEventMsgData(**(await state.get_data()))
    file_id = None
    text = None

    # Получаем информацию о стикере
    try:
        sticker = message.sticker
        file_id = sticker.file_id
    except Exception:
        text = get_text(user.language,"admins_editor_event_msg", "error_extract_data")

    if text:
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=text,
            reply_markup=await back_in_sticker_editor(user.language, data.ui_image_key, data.current_page)
        )
        return

    await admin_module.stickers_service.update_sticker(
        key=data.event_message_key,
        data=UpdateStickerDTO(file_id=file_id),
        make_commit=True,
        filling_redis=True,
    )
    await show_sticker_editor(
        event_msg_key=data.event_message_key,
        current_page=data.current_page,
        user=user,
        new_message=True,
        admin_module=admin_module,
        messages_service=messages_service,
    )

