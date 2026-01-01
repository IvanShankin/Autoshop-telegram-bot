from typing import Optional

from src.bot_actions.bot_instance import get_bot_logger, GLOBAL_RATE_LIMITER
from src.services.secrets.secret_conf import get_secret_conf
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply, FSInputFile, \
    Message

from src.bot_actions.bot_instance import get_bot
from src.services.database.system.actions import get_ui_image, update_ui_image
from src.services.database.system.actions import get_settings
from src.services.filesystem.actions import check_file_exists
from src.utils.core_logger import logger


async def send_message(
    chat_id: int,
    message: str = None,
    image_key: str = None,
    fallback_image_key: str = None,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
    parse_mode: Optional[str] = "HTML",
    always_show_photos: bool = False
) -> Message | None:
    """
    Отправит сообщение по-указанному chat_id, если есть image_key, то отправит фото с сообщением.
    """
    if not message and not image_key:
        raise ValueError("При отсылке нового сообщения необходимо указать хотя бы 'message' или 'image_key'")

    await GLOBAL_RATE_LIMITER.acquire()

    bot = await get_bot()
    if image_key:
        ui_image = await get_ui_image(image_key)
        if ui_image and (ui_image.show or always_show_photos): # если есть изображение по данному пути и его можно показывать
            try:
                # Если уже есть file_id — отправляем без загрузки
                if ui_image.file_id:
                    try:
                        return await bot.send_photo(
                            chat_id=chat_id,
                            photo=ui_image.file_id,
                            caption=message,
                            parse_mode=parse_mode,
                            reply_markup=reply_markup
                        )
                    except Exception as e:
                        # file_id устарел или недействителен
                        if "file" in str(e).lower() or "not found" in str(e).lower():
                            logger.warning(f"[send_message] file_id недействителен для {ui_image.key}, переотправляем файл.")

                        if check_file_exists(ui_image.file_path):
                            # отправляем файл с диска
                            photo = FSInputFile(ui_image.file_path)
                            msg = await bot.send_photo(
                                chat_id=chat_id,
                                photo=photo,
                                caption=message,
                                parse_mode=parse_mode,
                                reply_markup=reply_markup
                            )

                            # Сохраняем file_id для будущего использования
                            new_file_id = msg.photo[-1].file_id
                            await update_ui_image(key=ui_image.key, show=ui_image.show, file_id=new_file_id)

                            return msg

                elif check_file_exists(ui_image.file_path):
                    # Иначе — отправляем файл с диска
                    photo = FSInputFile(ui_image.file_path)
                    msg = await bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=message,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )

                    # Сохраняем file_id для будущего использования
                    new_file_id = msg.photo[-1].file_id
                    await update_ui_image(key=ui_image.key, show=ui_image.show, file_id=new_file_id)

                    return msg
                else:
                    text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{image_key}'"
                    logger.warning(text)
                    await send_log(text)

            except Exception as e:
                logger.exception(f"#Ошибка при отправке фото: {str(e)}")

        # если не нашли ui_image или не надо отсылать его (not ui_image.show)
        elif (not ui_image or ui_image and not ui_image.show) and fallback_image_key:
            text = ''
            if not ui_image:
                text = f"#Не_найдено_фото [send_message]. \nimage_key='{image_key}'"
                logger.warning(text)

            ui_image = await get_ui_image(fallback_image_key)
            if ui_image:
                if ui_image.file_id:
                    return await bot.send_photo(
                        chat_id=chat_id,
                        photo=ui_image.file_id,
                        caption=message,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )
                elif check_file_exists(ui_image.file_path):
                    photo = FSInputFile(ui_image.file_path)
                    msg = await bot.send_photo(chat_id, photo=photo, caption=message, parse_mode=parse_mode, reply_markup=reply_markup)

                    # Сохраняем file_id для будущего использования
                    new_file_id = msg.photo[-1].file_id
                    await update_ui_image(key=ui_image.key, show=ui_image.show, file_id=new_file_id)
                    return msg
                else:
                    text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{fallback_image_key}'"
                    logger.warning(text)
                    await send_log(text)

            if not ui_image:
                await send_log(text) # лучше после отправки пользователю
        elif not ui_image:
            # если нет замены для фото
            text = f"#Не_найдено_фото [send_message]. \nget_ui_image='{image_key}'"
            logger.warning(text)
            await send_log(text)

    try:
        if not message:
            message = "None"

        return await bot.send_message(chat_id, text=message, parse_mode=parse_mode, reply_markup=reply_markup)

    except Exception as e:
        logger.exception(f"#Ошибка при отправке сообщения. Ошибка: {str(e)}")

async def send_log(text: str, channel_for_logging_id: int = None):
    """
    :param text: Длинна должна быть в пределах 1 - 4096 символов
    :param channel_for_logging_id: если не передавать то возьмёт сам из настроек
    """

    # формируем сообщения разбивая по максимальной длине (4096)
    parts = []
    for i in range(0, len(text), 4096):
        parts.append(text[i:i + 4096])


    if not channel_for_logging_id:
        settings = await get_settings()
        channel_for_logging_id = settings.channel_for_logging_id

    bot = await get_bot_logger()

    try:
        for message in parts:
            await bot.send_message(int(channel_for_logging_id), message)
    except Exception as e:
        settings = await get_settings()
        message_error = (
            f"Не удалось отправить сообщение в канал с логами.\n"
            f"ID используемого канала: {channel_for_logging_id} "
            f"\n\nОшибка: {str(e)}"
        )
        logger.error(message_error)

        try:
            if settings.support_username:
                await bot.send_message(settings.support_username, message_error)
                for message in parts:
                    await bot.send_message(settings.support_username,message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения support. Ошибка: {str(e)}")

        try:
            await bot.send_message(get_secret_conf().MAIN_ADMIN, message_error)
            for message in parts:
                await bot.send_message(get_secret_conf().MAIN_ADMIN, message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения MAIN_ADMIN. Ошибка: {str(e)}")
