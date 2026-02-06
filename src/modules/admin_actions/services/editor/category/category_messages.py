from typing import Any, AsyncGenerator

from aiogram.types import Message

from src.bot_actions.messages import edit_message, send_message
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def message_info_load_file(user: Users) -> AsyncGenerator[Message, None]:
    """Первый вызов: сообщение о скачивание файла. Второй вызов: сообщение об обработке файла"""
    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins_editor_category",
            "wait_load_products"
        )
    )
    message_info = await send_message(
        user.user_id,
        get_text(user.language, "admins_editor_category", "file_uploaded_to_the_server")
    )

    yield message_info

    await edit_message(
        user.user_id,
        message_info.message_id,
        get_text(
            user.language,
            "admins_editor_category",
            "file_successfully_uploaded"
        )
    )

    yield message_info



def make_result_msg(
        user: Users,
        successfully_added: int,
        total_processed: int,
        mark_invalid_acc:  Any,
        mark_duplicate_acc: Any,
        tg_acc: bool = False
) -> str:
    result_message = get_text(
        user.language,
        "admins_editor_category",
        "products_integration_was_successful"
    ).format(successfully_added=successfully_added, total_processed=total_processed)
    if mark_invalid_acc:
        result_message += get_text(
            user.language,
            "admins_editor_category",
            "failed_to_extract_some_accounts"
        ).format(
            acc_from=  get_text(
                user.language,
                "admins_editor_category",
                "files" if tg_acc else "lines"
            )
        )
    if mark_duplicate_acc:
        result_message += get_text(
            user.language,
            "admins_editor_category",
            "some_accounts_already_in_bot"
        )
    return result_message
