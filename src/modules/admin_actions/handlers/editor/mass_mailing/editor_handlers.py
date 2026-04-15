import io
from typing import Optional

import validators
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.exceptions import TextTooLong
from src.models.read_models import UsersDTO
from src.models.update_models.admins import UpdateMessageForSending
from src.modules.admin_actions.keyboards import editor_message_mailing_kb
from src.modules.admin_actions.keyboards.editors.mass_mailing_kb import confirm_start_mailing_kb, \
    change_mailing_photo_kb, change_mailing_text_kb, back_in_change_mailing_text_kb, change_mailing_btn_url_kb, \
    back_in_editor_mes_mailing_kb
from src.modules.admin_actions.state import GetImageMassMailing, GetTextMassMailing
from src.modules.admin_actions.state.editors.editor_mass_mailing import GetBtnUrlMassMailing

from src.utils.i18n import get_text


router = Router()


async def show_editor_mes_mailing(
    user: UsersDTO,
    state: FSMContext,
    new_message: bool,
    admin_module: AdminModule,
    messages_service: Messages,
    callback: Optional[CallbackQuery] = None,
):
    await state.clear()

    message_data = await admin_module.message_for_sending_service.get_msg(user.user_id)
    ui_image = await admin_module.ui_images_service.get_ui_image(message_data.ui_image_key)

    image_key = message_data.ui_image_key if ui_image.show else None
    reply_markup = editor_message_mailing_kb(
        user.language, admin_module=admin_module, button_url=message_data.button_url
    )

    if image_key and messages_service.mass_tg_mailing.visible_text_length(message_data.content) >= 1024:
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "warning_message_too_long"
        )
    else:
        message = message_data.content

    if not message: # пустое сообщение
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "placeholder_for_message"
        )

    if new_message:
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=message,
            image_key=image_key,
            reply_markup=reply_markup
        )
        return

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        image_key=image_key,
        reply_markup=reply_markup
    )


async def edit_message_change_photo(
    user: UsersDTO,
    callback: CallbackQuery,
    state: FSMContext,
    admin_module: AdminModule,
    messages_service: Messages,
):
    message_data = await admin_module.message_for_sending_service.get_msg(user.user_id)
    ui_image = await admin_module.ui_images_service.get_ui_image(message_data.ui_image_key)

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "send_photo_as_document"
        ),
        reply_markup=change_mailing_photo_kb(user.language, current_show_image=ui_image.show)
    )
    await state.set_state(GetImageMassMailing.get_new_image)


@router.callback_query(F.data == "editor_mes_mailing")
async def editor_mes_mailing(
    callback: CallbackQuery, state: FSMContext,user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await show_editor_mes_mailing(
        user=user,
        state=state,
        new_message=False,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service
    )


@router.callback_query(F.data == "confirm_start_mailing")
async def editor_mes_mailing(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "confirmation_broadcast_to_all_users"
        ).format(need_seconds=await admin_module.user_service.get_quantity_users() // admin_module.conf.different.rate_send_msg_limit),
        reply_markup=confirm_start_mailing_kb(user.language)
    )


@router.callback_query(F.data == "start_mass_mailing")
async def start_mass_mailing(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    i = 0
    quantity_successfully = 0
    quantity_users = await admin_module.user_service.get_quantity_users()
    message_data = await admin_module.message_for_sending_service.get_msg(user.user_id)
    ui_image = await admin_module.ui_images_service.get_ui_image(message_data.ui_image_key)
    message = None

    try:
        async for user_id, ok, exc in messages_service.mass_tg_mailing.broadcast_message_generator(
            text=message_data.content,
            admin_id=user.user_id,
            photo_path=admin_module.path_builder.build_path_ui_image(file_name=ui_image.file_name),
            show_image=ui_image.show,
            button_url=message_data.button_url,
        ):
            i += 1

            if ok:
                quantity_successfully += 1

            if i % 50 == 0: # каждый 50 вызов
                await messages_service.edit_msg.edit(
                    chat_id=user.user_id,
                    message_id=callback.message.message_id,
                    message=get_text(
                        user.language,
                        "admins_editor_mass_mailing",
                        "mailing_statistics"
                    ).format(quantity_successfully=quantity_successfully, quantity_sent_total=i, quantity_users=quantity_users)
                )
    except TextTooLong:
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "warning_message_too_long"
        )
    except FileNotFoundError:
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "photo_not_found"
        )

    # если не вызвалась ошибка
    if not message:
        message = get_text(
            user.language,
            "admins_editor_mass_mailing",
            "mailing_completed"
        ).format(
            result=get_text(
                user.language,
                "admins_editor_mass_mailing",
                "mailing_statistics"
            ).format(quantity_successfully=quantity_successfully, quantity_sent_total=i, quantity_users=quantity_users)
        )

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        reply_markup=back_in_editor_mes_mailing_kb(user.language)
    )


@router.callback_query(F.data == "change_mailing_photo")
async def change_mailing_photo(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await edit_message_change_photo(
        user=user, callback=callback, state=state, admin_module=admin_module, messages_service=messages_service
    )


@router.message(GetImageMassMailing.get_new_image, F.document)
async def get_new_image(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    doc = message.document
    if not doc.mime_type.startswith("image/"): # Проверяем, что это действительно изображение
        text = get_text(user.language,"admins_editor_event_msg", "this_is_not_image")

    elif doc.file_size > admin_module.conf.limits.max_size_bytes: # Проверяем размер, известный Telegram (без скачивания)
        text = get_text(
            user.language,
            "admins_editor_category",
            "file_to_many_long"
        ).format(max_size_mb=admin_module.conf.limits.max_size_mb)
    else:
        file = await message.bot.get_file(doc.file_id)

        # Скачиваем файл в поток
        byte_stream = io.BytesIO()
        await message.bot.download_file(file.file_path, byte_stream)

        # Преобразуем поток в bytes
        file_bytes = byte_stream.getvalue()
        await admin_module.message_for_sending_service.update_msg(
            data=UpdateMessageForSending(user_id=user.user_id,),
            file_bytes=file_bytes,
            make_commit=True,
        )
        await show_editor_mes_mailing(
            user=user, state=state, new_message=True, admin_module=admin_module, messages_service=messages_service
        )
        return

    message_data = await admin_module.message_for_sending_service.get_msg(user.user_id)
    ui_image = await admin_module.ui_images_service.get_ui_image(message_data.ui_image_key)
    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=text,
        reply_markup=change_mailing_photo_kb(user.language, current_show_image=ui_image.show)
    )


@router.callback_query(F.data.startswith("update_show_mailing_image:"))
async def change_mailing_photo(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    new_show = bool(int(callback.data.split(":")[1]))

    await admin_module.message_for_sending_service.update_msg(
        data=UpdateMessageForSending(user_id=user.user_id),
        show_image=new_show,
        make_commit=True,
        filling_redis=True,
    )
    await edit_message_change_photo(
        user=user, callback=callback, state=state, admin_module=admin_module, messages_service=messages_service
    )


@router.callback_query(F.data == "change_mailing_text")
async def change_mailing_text(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "instructions_for_sending_text"
        ),
        reply_markup=change_mailing_text_kb(user.language),
        parse_mode=None
    )
    await state.set_state(GetTextMassMailing.get_new_text)


@router.callback_query(F.data == "open_mailing_tip")
async def open_mailing_tip(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "basic_formatting_tags"
        ),
        reply_markup=back_in_change_mailing_text_kb(user.language),
        parse_mode=None
    )


@router.message(GetTextMassMailing.get_new_text)
async def get_new_text(
        message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await admin_module.message_for_sending_service.update_msg(
        data=UpdateMessageForSending(user_id=user.user_id, content=message.text),
        make_commit=True,
    )
    await show_editor_mes_mailing(
        user=user, state=state, new_message=True, admin_module=admin_module, messages_service=messages_service
    )


@router.callback_query(F.data == "change_mailing_btn_url")
async def change_mailing_btn_url(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    message_data = await admin_module.message_for_sending_service.get_msg(user.user_id)
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_mass_mailing",
            "current_link"
        ).format(url=message_data.button_url if message_data.button_url else ""),
        reply_markup=change_mailing_btn_url_kb(user.language),
    )
    await state.set_state(GetBtnUrlMassMailing.get_new_btn_url)


@router.callback_query(F.data == "delete_mailing_btn_url")
async def delete_mailing_btn_url(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await admin_module.message_for_sending_service.update_msg(
        data=UpdateMessageForSending(user_id=user.user_id, button_url=None),
        make_commit=True,
    )
    await show_editor_mes_mailing(
        user=user, state=state, new_message=True, admin_module=admin_module, messages_service=messages_service
    )


@router.message(GetBtnUrlMassMailing.get_new_btn_url)
async def get_new_text(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    new_url = message.text
    if not validators.url(new_url):
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=get_text(
                user.language,
                "admins_editor_mass_mailing",
                "incorrect_url"
            ),
            reply_markup=change_mailing_btn_url_kb(user.language),
        )
        await state.set_state(GetBtnUrlMassMailing.get_new_btn_url)
        return

    await admin_module.message_for_sending_service.update_msg(
        data=UpdateMessageForSending(user_id=user.user_id, button_url=new_url),
        make_commit=True,
    )
    await show_editor_mes_mailing(
        user=user, state=state, new_message=True, admin_module=admin_module, messages_service=messages_service
    )