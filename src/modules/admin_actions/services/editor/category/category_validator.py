from typing import List

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Document

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.modules.admin_actions.keyboards.editors.category_kb import in_category_kb
from src.models.read_models import CategoryFull, UsersDTO
from src.utils.i18n import get_text


async def check_valid_file(
    doc: Document,
    user: UsersDTO,
    state: FSMContext,
    expected_formats: List[str],
    set_state: State,
    admin_module: AdminModule,
    messages_service: Messages,
):
    """Проверит файл на валидный формат и на необходимый размер,
    если один из этих условий не будет выполнено,
    то отошлёт соответствующие сообщение, установит состояние 'set_state' и вернёт False"""
    file_name = doc.file_name
    extension = file_name.split('.')[-1].lower()  # пример: "zip"
    if extension not in expected_formats:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(
                user.language,
                "admins_editor_category",
                "file_format_not_supported"
            ).format(extensions_list=expected_formats)
        )
        await state.set_state(set_state)
        return False

    if doc.file_size > admin_module.conf.limits.max_download_size:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(
                user.language,
                "admins_editor_category",
                "file_to_many_long"
            ).format(max_size_mb=admin_module.conf.limits.max_download_size)
        )
        await state.set_state(set_state)
        return False

    return True


async def check_category_is_acc_storage(category: CategoryFull, user: UsersDTO, messages_service: Messages,) -> bool:
    """
    Проверит что категория - хранилище аккаунтов. Еслине хранит, то отправит сообщение, что необходимо сделать хранилищем
    :return bool: True если хранит, иначе False
    """
    if not category.is_product_storage:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(user.language,"admins_editor_category","first_make_this_category_storage"),
            reply_markup=in_category_kb(
                language=user.language,
                category_id=category.category_id
            )
        )
        return False
    return True


