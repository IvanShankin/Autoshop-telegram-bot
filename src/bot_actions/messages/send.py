import os.path
from pathlib import Path
from typing import Optional

from aiogram.exceptions import TelegramBadRequest

from src.bot_actions.bot_instance import get_bot_logger
from src.config import get_config, get_global_rate_limit
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply, FSInputFile, \
    Message

from src.bot_actions.bot_instance import get_bot
from src.services.database.system.actions import get_ui_image, update_ui_image, get_file, update_file
from src.services.database.system.actions import get_settings
from src.services.filesystem.actions import check_file_exists
from src.utils.core_logger import get_logger


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

    await get_global_rate_limit().acquire()

    bot = await get_bot()
    logger = get_logger(__name__)
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
            await get_global_rate_limit().acquire()
            await bot.send_message(int(channel_for_logging_id), message)
    except Exception as e:
        logger = get_logger(__name__)

        settings = await get_settings()
        message_error = (
            f"Не удалось отправить сообщение в канал с логами.\n"
            f"ID используемого канала: {channel_for_logging_id} "
            f"\n\nОшибка: {str(e)}"
        )
        logger.error(message_error)

        try:
            if settings.support_username:
                await get_global_rate_limit().acquire()
                await bot.send_message(settings.support_username, message_error)
                for message in parts:
                    await get_global_rate_limit().acquire()
                    await bot.send_message(settings.support_username,message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения support. Ошибка: {str(e)}")

        try:
            await get_global_rate_limit().acquire()
            await bot.send_message(get_config().env.main_admin, message_error)
            for message in parts:
                await get_global_rate_limit().acquire()
                await bot.send_message(get_config().env.main_admin, message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения MAIN_ADMIN. Ошибка: {str(e)}")


async def send_file(
    chat_id: int,
    file_key: str,
    message: Optional[str] = None,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
    parse_mode: Optional[str] = "HTML",
    type_based: Optional[bool] = False,
    one_attempt: bool = False
):
    """
    Отошлёт файл по указанному `chat_id`
    :param file_key:
    :param type_based: Отошлёт файл в зависимости от его типа. Если у него расширение фото, то отошлёт как фото и т.д.
    :param one_attempt: Флаг попытаться отправить только раз.
    :except FileNotFoundError: Если на диске не нашёлся файл
    :except ValueError: Если такого ключа нет в БД
    """
    bot = await get_bot()
    conf = get_config()

    file = await get_file(file_key)
    if not file:
        raise ValueError(f"Файл по ключу: '{file_key}' не найден")

    if file.file_tg_id:
        document = file.file_tg_id
    else:
        full_file_path = conf.paths.files_dir / Path(file.file_path)
        if not os.path.isfile(full_file_path):
            raise FileNotFoundError()

        document = FSInputFile(full_file_path)

    await get_global_rate_limit().acquire()
    try:
        message = await bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=message,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as e:
        logger = get_logger(__name__)
        logger.warning(f"При попытки отослать документ произошла ошибка: {str(e)}")
        # может быть из-за плохого file_tg_id
        await update_file(file_key, file_tg_id=None)
        if not one_attempt and file.file_tg_id:
            await send_file(
                chat_id=chat_id,
                file_key=file_key,
                message=message,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                type_based=type_based,
                one_attempt=True
            )
        return

    await update_file(file_key, file_tg_id=message.document.file_id)
