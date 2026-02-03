from typing import List

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Document

from src.bot_actions.messages import send_message
from src.config import get_config
from src.modules.admin_actions.keyboards import back_in_category_kb
from src.services.database.categories.models import CategoryFull
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def check_valid_file(doc: Document, user: Users, state: FSMContext, expected_formats: List[str], set_state: State):
    """Проверит файл на валидный формат и на необходимый размер,
    если один из этих условий не будет выполнено,
    то отошлёт соответствующие сообщение, установит состояние 'set_state' и вернёт False"""
    file_name = doc.file_name
    extension = file_name.split('.')[-1].lower()  # пример: "zip"
    if extension not in expected_formats:
        await send_message(
            user.user_id,
            get_text(
                user.language,
                "admins_editor_category",
                "This file format is not supported, please send a file with one of these extensions: {extensions_list}"
            ).format(extensions_list=expected_formats)
        )
        await state.set_state(set_state)
        return False

    if doc.file_size > get_config().limits.max_download_size:
        await send_message(
            user.user_id,
            get_text(
                user.language,
                "admins_editor_category",
                "The file is too large. The maximum size is {max_size_file} MB. \n\nPlease send a different file"
            ).format(extensions_list=get_config().limits.max_download_size)
        )
        await state.set_state(set_state)
        return False

    return True


async def check_category_is_acc_storage(category: CategoryFull, user: Users) -> bool:
    """
    Проверит что категория - хранилище аккаунтов. Еслине хранит, то отправит сообщение, что необходимо сделать хранилищем
    :return bool: True если хранит, иначе False
    """
    if not category.is_product_storage:
        await send_message(
            user.user_id,
            get_text(user.language,"admins_editor_category","First, make this category a food storage area"),
            reply_markup=back_in_category_kb(
                language=user.language,
                category_id=category.category_id,
                i18n_key = "In category"
            )
        )
        return False
    return True


