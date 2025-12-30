import io

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.config import MAX_SIZE_BYTES, MAX_SIZE_MB
from src.modules.admin_actions.keyboards import images_list_kb, image_editor, back_in_image_editor
from src.modules.admin_actions.schemas import GetNewImageData
from src.modules.admin_actions.state import GetNewImage
from src.services.database.system.actions.actions import  update_ui_image, get_ui_image, \
    delete_ui_image, create_ui_image
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()


async def show_image_editor(
    ui_image_key: str,
    current_page: int,
    user: Users,
    new_message: bool = False,
    callback: CallbackQuery = None
):
    ui_image = await get_ui_image(ui_image_key)

    if not ui_image:
        text = get_text(user.language, "admins_editor_images", "This photo no longer exists")
        if callback:
            await callback.answer(text, show_alert=True)
        else:
            await send_message(chat_id=user.user_id, message=text)
        return

    message = get_text(
        user.language, "admins_editor_images", "Where is it used: {where} \nShow: {show}"
    ).format(where=get_text(user.language, "ui_images_description", ui_image_key), show=ui_image.show)

    reply_markup = image_editor(user.language, ui_image_key, current_show=ui_image.show,current_page=current_page)

    if new_message:
        await send_message(chat_id=user.user_id,message=message,image_key=ui_image_key, reply_markup=await reply_markup)
        return

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=message,
        image_key=ui_image_key,
        reply_markup=await reply_markup,
        always_show_photos=True
    )


@router.callback_query(F.data.startswith("images_editor_list:"))
async def images_editor_list(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(':')[1])

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=await images_list_kb(user.language, current_page)
    )


@router.callback_query(F.data.startswith("edit_image:"))
async def edit_image(callback: CallbackQuery, user: Users):
    ui_image_key = str(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])
    await show_image_editor(
        ui_image_key=ui_image_key,
        current_page=current_page,
        user=user,
        callback=callback
    )


@router.callback_query(F.data.startswith("ui_image_update_show:"))
async def ui_image_update_show(callback: CallbackQuery, user: Users):
    ui_image_key = callback.data.split(':')[1]
    new_show = bool(int(callback.data.split(':')[2]))
    current_page = int(callback.data.split(':')[3])
    await update_ui_image(ui_image_key, show=new_show)
    await callback.answer(get_text(user.language, "miscellaneous", "Successfully updated"), show_alert=True)
    await show_image_editor(
        ui_image_key=ui_image_key,
        current_page=current_page,
        user=user,
        callback=callback
    )


@router.callback_query(F.data.startswith("change_ui_image:"))
async def change_ui_image(callback: CallbackQuery, state: FSMContext, user: Users):
    ui_image_key = str(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message="Send a new image. \n\nNote: Please provide a document for best photo quality",
        reply_markup=await back_in_image_editor(user.language, ui_image_key, current_page)
    )
    await state.update_data(ui_image_key=ui_image_key, current_page=current_page)
    await state.set_state(GetNewImage.get_new_image)


@router.message(GetNewImage.get_new_image, F.document)
async def change_ui_image_result(message: Message, state: FSMContext, user: Users):
    doc = message.document
    data = GetNewImageData(**(await state.get_data()))
    # обновляем и выводим сообщение

    if not doc.mime_type.startswith("image/"): # Проверяем, что это действительно изображение
        text = get_text(user.language,"admins_editor_images", "This is not an image. Send it as a document")
    elif doc.file_size > MAX_SIZE_BYTES: # Проверяем размер, известный Telegram (без скачивания)
        text = get_text(
            user.language,
            "admins_editor_category",
            "The file is too large — maximum {max_size_mb} MB. \n\nTry again"
        ).format(max_size_mb=MAX_SIZE_MB)
    else:
        # Получаем объект файла
        file = await message.bot.get_file(doc.file_id)

        # Скачиваем файл в поток
        byte_stream = io.BytesIO()
        await message.bot.download_file(file.file_path, byte_stream)

        # Преобразуем поток  bytes
        file_bytes = byte_stream.getvalue()

        await delete_ui_image(key=data.ui_image_key)
        await create_ui_image(key=data.ui_image_key, file_data=file_bytes)

        await show_image_editor(ui_image_key=data.ui_image_key,current_page=data.current_page,user=user,new_message=True)
        return

    # тут только отсылка о неуспехе
    await send_message(
        chat_id=user.user_id,
        message=text,
        reply_markup= await back_in_image_editor(user.language, data.ui_image_key, data.current_page)
    )


