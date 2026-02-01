import io
from typing import Optional

import validators
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.bot_actions.messages.mass_tg_mailing import visible_text_length, broadcast_message_generator
from src.config import get_config
from src.exceptions import TextTooLong
from src.modules.admin_actions.keyboards import editor_message_mailing_kb
from src.modules.admin_actions.keyboards.editors.mass_mailing_kb import confirm_start_mailing_kb, \
    change_mailing_photo_kb, change_mailing_text_kb, back_in_change_mailing_text_kb, change_mailing_btn_url_kb, \
    back_in_editor_mes_mailing_kb
from src.modules.admin_actions.state import GetImageMassMailing, GetTextMassMailing
from src.modules.admin_actions.state.editors.editor_mass_mailing import GetBtnUrlMassMailing
from src.services.database.admins.actions import get_message_for_sending, update_message_for_sending
from src.services.database.users.actions.action_user import get_quantity_users
from src.services.database.users.models import Users
from src.services.filesystem.media_paths import create_path_ui_image
from src.utils.i18n import get_text

router = Router()


async def show_editor_mes_mailing(
    user: Users,
    state: FSMContext,
    new_message: bool,
    callback: Optional[CallbackQuery] = None
):
    await state.clear()

    message_data = await get_message_for_sending(user.user_id)
    image_key = message_data.ui_image_key if message_data.ui_image.show else None
    reply_markup = editor_message_mailing_kb(user.language, button_url=message_data.button_url)

    if image_key and visible_text_length(message_data.content) >= 1024:
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "Warning! \nThe message is too long. \n\n"
            "For a message with a photo, please attach a text <b>no more than 1024</b> characters long \n"
            "For a message without a photo, please attach a text <b>no more than 4096</b> characters long"
        )
    else:
        message = message_data.content

    if not message: # пустое сообщение
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "There will be a message here"
        )

    if new_message:
        await send_message(
            chat_id=user.user_id,
            message=message,
            image_key=image_key,
            reply_markup=reply_markup
        )
        return

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        image_key=image_key,
        reply_markup=reply_markup
    )


async def edit_message_change_photo(user: Users, callback: CallbackQuery, state: FSMContext):
    message_data = await get_message_for_sending(user.user_id)
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "Send a photo as a document"
        ),
        reply_markup=change_mailing_photo_kb(user.language, current_show_image=message_data.ui_image.show)
    )
    await state.set_state(GetImageMassMailing.get_new_image)


@router.callback_query(F.data == "editor_mes_mailing")
async def editor_mes_mailing(callback: CallbackQuery, state: FSMContext, user: Users):
    await show_editor_mes_mailing(user=user, state=state, new_message=False, callback=callback)


@router.callback_query(F.data == "confirm_start_mailing")
async def editor_mes_mailing(callback: CallbackQuery, user: Users):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "Are you sure you want to broadcast this message to all users? \n\n"
            "This will take approximately: {need_seconds} seconds"
        ).format(need_seconds=await get_quantity_users() // get_config().different.rate_send_msg_limit),
        reply_markup=confirm_start_mailing_kb(user.language)
    )


@router.callback_query(F.data == "start_mass_mailing")
async def start_mass_mailing(callback: CallbackQuery, user: Users):
    i = 0
    quantity_successfully = 0
    quantity_users = await get_quantity_users()
    message_data = await get_message_for_sending(user.user_id)
    message = None

    try:
        async for user_id, ok, exc in broadcast_message_generator(
            text=message_data.content,
            admin_id=user.user_id,
            photo_path=create_path_ui_image(file_name=message_data.ui_image.file_name),
            button_url=message_data.button_url,
        ):
            i += 1

            if ok:
                quantity_successfully += 1

            if i % 50 == 0: # каждый 50 вызов
                await edit_message(
                    chat_id=user.user_id,
                    message_id=callback.message.message_id,
                    message=get_text(
                        user.language,
                        "admins_editor_mass_mailing",
                        "Sent successfully: {quantity_successfully} \n"
                        "Total sent: {quantity_sent_total} \n"
                        "Total users: {quantity_users}"
                    ).format(quantity_successfully=quantity_successfully, quantity_sent_total=i, quantity_users=quantity_users)
                )
    except TextTooLong:
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "Warning! \nThe message is too long. \n\n"
            "For a message with a photo, please attach a text <b>no more than 1024</b> characters long \n"
            "For a message without a photo, please attach a text <b>no more than 4096</b> characters long"
        )
    except FileNotFoundError:
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "The photo could not be found. Please re-attach it"
        )

    # если не вызвалась ошибка
    if not message:
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "Mailing completed \n\n{result}"
        ).format(
            result=get_text(
                user.language,
                "admins_editor_mass_mailing",
                "Sent successfully: {quantity_successfully} \n"
                "Total sent: {quantity_sent_total} \n"
                "Total users: {quantity_users}"
            ).format(quantity_successfully=quantity_successfully, quantity_sent_total=i, quantity_users=quantity_users)
        )

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=back_in_editor_mes_mailing_kb(user.language)
    )


@router.callback_query(F.data == "change_mailing_photo")
async def change_mailing_photo(callback: CallbackQuery, state: FSMContext, user: Users):
    await edit_message_change_photo(user=user, callback=callback, state=state)


@router.message(GetImageMassMailing.get_new_image, F.document)
async def get_new_image(message: Message, state: FSMContext, user: Users):
    doc = message.document
    if not doc.mime_type.startswith("image/"): # Проверяем, что это действительно изображение
        text = get_text(user.language,"admins_editor_images", "This is not an image. Send it as a document")

    elif doc.file_size > get_config().limits.max_size_bytes: # Проверяем размер, известный Telegram (без скачивания)
        text = get_text(
            user.language,
            "admins_editor_category",
            "The file is too large — maximum {max_size_mb} MB. \n\nTry again"
        ).format(max_size_mb=get_config().limits.max_size_mb)
    else:
        file = await message.bot.get_file(doc.file_id)

        # Скачиваем файл в поток
        byte_stream = io.BytesIO()
        await message.bot.download_file(file.file_path, byte_stream)

        # Преобразуем поток в bytes
        file_bytes = byte_stream.getvalue()
        await update_message_for_sending(user_id=user.user_id, file_bytes=file_bytes)
        await show_editor_mes_mailing(user=user, state=state, new_message=True)
        return

    message_data = await get_message_for_sending(user.user_id)
    await send_message(
        chat_id=user.user_id,
        message=text,
        reply_markup=change_mailing_photo_kb(user.language, current_show_image=message_data.ui_image.show)
    )


@router.callback_query(F.data.startswith("update_show_mailing_image:"))
async def change_mailing_photo(callback: CallbackQuery, state: FSMContext, user: Users):
    new_show = bool(int(callback.data.split(":")[1]))
    await update_message_for_sending(user_id=user.user_id, show_image=new_show)
    await edit_message_change_photo(user=user, callback=callback, state=state)


@router.callback_query(F.data == "change_mailing_text")
async def change_mailing_text(callback: CallbackQuery, state: FSMContext, user: Users):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "Send the text that will be used to send the message.\n\n"
            "To apply text formatting, use HTML markup by placing the desired text in tags.\n"
            "Example: <b>Desired text.</b> \n"
            "- This text will be bold.\n"
            "See the tooltip for tag options\n\n"
            "For a message with a photo, attach a text no more than 1024 characters long.\n"
            "For a message without a photo, attach a text no more than 4096 characters long."
        ),
        reply_markup=change_mailing_text_kb(user.language),
        parse_mode=None
    )
    await state.set_state(GetTextMassMailing.get_new_text)


@router.callback_query(F.data == "open_mailing_tip")
async def open_mailing_tip(callback: CallbackQuery, state: FSMContext, user: Users):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "Basic formatting tags: \n"
            "<b> bold text </b> \n"
            "<i> italic </i> \n"
            "<u> underlined text </u> \n"
            "<s> ~~strikethrough text~~ </s> \n"
            "<code> monospace code </code> \n"
            "<pre> preformatted text block </pre> \n"
            "<tg-spoiler> spoiler (hidden text) </tg-spoiler> \n\n"
            "Links: \n"
            '<a href="URL">link text</a> - regular link\n'
            '<a href="tg://user?id=123456">user mention</a> - user mention'
        ),
        reply_markup=back_in_change_mailing_text_kb(user.language),
        parse_mode=None
    )


@router.message(GetTextMassMailing.get_new_text)
async def get_new_text(message: Message, state: FSMContext, user: Users):
    await update_message_for_sending(user_id=user.user_id, content=message.text)
    await show_editor_mes_mailing(user=user, state=state, new_message=True)


@router.callback_query(F.data == "change_mailing_btn_url")
async def change_mailing_btn_url(callback: CallbackQuery, state: FSMContext, user: Users):
    message_data = await get_message_for_sending(user.user_id)
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "Current link: \n<code>{url}</code>"
        ).format(url=message_data.button_url if message_data.button_url else ""),
        reply_markup=change_mailing_btn_url_kb(user.language),
    )
    await state.set_state(GetBtnUrlMassMailing.get_new_btn_url)


@router.callback_query(F.data == "delete_mailing_btn_url")
async def delete_mailing_btn_url(callback: CallbackQuery, state: FSMContext, user: Users):
    await update_message_for_sending(user_id=user.user_id, button_url=None)
    await show_editor_mes_mailing(user=user, state=state, new_message=False, callback=callback)


@router.message(GetBtnUrlMassMailing.get_new_btn_url)
async def get_new_text(message: Message, state: FSMContext, user: Users):
    new_url = message.text
    if not validators.url(new_url):
        await send_message(
            chat_id=user.user_id,
            message=get_text(
                user.language,
                "admins_editor_mass_mailing",
                "The URL you entered is incorrect. Please try again"
            ),
            reply_markup = change_mailing_btn_url_kb(user.language),
        )
        await state.set_state(GetBtnUrlMassMailing.get_new_btn_url)
        return

    await update_message_for_sending(user_id=user.user_id, button_url=new_url)
    await show_editor_mes_mailing(user=user, state=state, new_message=True)