import uuid

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.config import get_config
from src.modules.admin_actions.keyboards import admin_mailing_kb, all_admin_mass_mailing_kb, show_sent_mass_message_kb
from src.modules.admin_actions.keyboards.editors.mass_mailing_kb import back_in_show_sent_mass_message_kb
from src.services.database.admins.actions.actions_admin import get_sent_mass_messages
from src.services.database.system.actions import create_ui_image, delete_ui_image
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data == "admin_mailing")
async def admin_promo(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=admin_mailing_kb(user.language)
    )


@router.callback_query(F.data.startswith("sent_message_list:"))
async def sent_message_list(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(":")[1])
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=await all_admin_mass_mailing_kb(user.language, current_page)
    )


@router.callback_query(F.data.startswith("show_sent_mass_message:"))
async def show_sent_mass_message(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(":")[1])
    msg_id = int(callback.data.split(":")[2])
    msg = await get_sent_mass_messages(msg_id)
    image_key = None

    if not msg:
        await callback.answer(
            get_text(
                user.language,
                "admins_editor_mass_mailing",
                "Message not found"
            ),
            show_alert=True
        )
        return

    if msg.photo_id and msg.photo_path:
        image_key = str(uuid.uuid4())

        with open(msg.photo_path, "rb") as f:
            file_data: bytes = f.read()
        await create_ui_image(image_key, file_data=file_data, file_id=msg.photo_id)

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=msg.content,
        image_key=image_key if image_key else None,
        reply_markup=show_sent_mass_message_kb(
            user.language,
            current_page=current_page,
            message_id=msg_id,
            button_url=msg.button_url
        )
    )

    if image_key:
        await delete_ui_image(image_key)


@router.callback_query(F.data.startswith("detail_mass_msg:"))
async def detail_mass_msg(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(":")[1])
    msg_id = int(callback.data.split(":")[2])
    msg = await get_sent_mass_messages(msg_id)

    if not msg:
        await callback.answer(
            get_text(
                user.language,
                "admins_editor_mass_mailing",
                "Message not found"
            ),
            show_alert=True
        )
        return

    message = get_text(
        user.language,
        "admins_editor_mass_mailing",
        "Message ID: {message_id} \n\n"
        "Admin ID who sent the mailing: {admin_id} \n"
        "Number of users who received messages: {number_received} \n"
        "Number of messages sent: {number_sent} \n"
        "Date of the event: {created_at} \n"
    ).format(
        message_id=msg.message_id,
        admin_id=msg.user_id,
        number_received=msg.number_received,
        number_sent=msg.number_sent,
        created_at=msg.created_at.strftime(get_config().different.dt_format)
    )

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=back_in_show_sent_mass_message_kb(
            user.language,
            current_page=current_page,
            message_id=msg_id,
            button_url=msg.button_url
        )
    )