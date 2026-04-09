from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.bot_actions.messages.send_stickers import send_sticker
from src.modules.admin_actions.keyboards.editors.event_message_kb import sticker_editor_kb, back_in_sticker_editor
from src.modules.admin_actions.schemas import UpdateEventMsgData
from src.modules.admin_actions.state.editors.editor_event_msg import UpdateEventMsg
from src.application._database.system.actions.actions import get_sticker, update_sticker
from src.database.models.users import Users
from src.utils.i18n import get_text


router = Router()


async def show_sticker_editor(
    event_msg_key: str,
    current_page: int,
    user: Users,
    new_message: bool = False,
    callback: CallbackQuery = None
):
    sticker = await get_sticker(event_msg_key)

    message = get_text(
        user.language, "admins_editor_event_msg", "where_used_and_indicate_show"
    ).format(
        where=get_text(user.language, "event_msg_description", event_msg_key),
        show=sticker.show if sticker else get_text(user.language, "miscellaneous", "no"),
        current=" " if sticker and sticker.file_id else get_text(user.language, "miscellaneous", "no")
    )

    reply_markup = sticker_editor_kb(user.language, event_msg_key, current_show=sticker.show,current_page=current_page)

    if new_message:
        await send_message(chat_id=user.user_id, message=message, reply_markup=await reply_markup)
    else:
        await edit_message(
            chat_id=user.user_id,
            message_id=callback.message.message_id,
            message=message,
            event_message_key="admin_panel",
            reply_markup=await reply_markup
        )


@router.callback_query(F.data.startswith("edit_sticker:"))
async def edit_sticker(callback: CallbackQuery, user: Users):
    event_msg_key = str(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    await show_sticker_editor(
        event_msg_key=event_msg_key,
        current_page=current_page,
        user=user,
        callback=callback
    )


@router.callback_query(F.data.startswith("sticker_update_show:"))
async def sticker_update_show(callback: CallbackQuery, user: Users):
    event_msg_key = callback.data.split(':')[1]
    new_show = bool(int(callback.data.split(':')[2]))
    current_page = int(callback.data.split(':')[3])

    await update_sticker(event_msg_key, show=new_show)
    await callback.answer(get_text(user.language, "miscellaneous", "successfully_updated"), show_alert=True)

    await show_sticker_editor(
        event_msg_key=event_msg_key,
        current_page=current_page,
        user=user,
        callback=callback
    )


@router.callback_query(F.data.startswith("show_current_sticker:"))
async def show_current_sticker(callback: CallbackQuery, user: Users):
    event_msg_key = callback.data.split(':')[1]
    sticker = await get_sticker(event_msg_key)

    if sticker and sticker.file_id:
        await send_sticker(chat_id=user.user_id, sticker_key=event_msg_key)
        return

    await callback.answer(
        text=get_text(user.language, "admins_editor_event_msg", "sticker_not_found"),
        show_alert=True
    )


@router.callback_query(F.data.startswith("change_sticker:"))
async def change_sticker(callback: CallbackQuery, state: FSMContext, user: Users):
    event_msg_key = str(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    await edit_message(
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
async def change_sticker_result(message: Message, state: FSMContext, user: Users):
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
        await send_message(
            chat_id=user.user_id,
            message=text,
            reply_markup=await back_in_sticker_editor(user.language, data.ui_image_key, data.current_page)
        )
        return

    await update_sticker(key=data.event_message_key, file_id=file_id)
    await show_sticker_editor(
        event_msg_key=data.event_message_key,
        current_page=data.current_page,
        user=user,
        new_message=True
    )

