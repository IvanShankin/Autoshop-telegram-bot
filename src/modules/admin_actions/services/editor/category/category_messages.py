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
            "Please wait for the accounts to load and don't touch anything!"
        )
    )
    message_info = await send_message(
        user.user_id,
        get_text(user.language, "admins_editor_category", "The file is uploaded to the server")
    )

    yield message_info

    await edit_message(
        user.user_id,
        message_info.message_id,
        get_text(
            user.language,
            "admins_editor_category",
            "The file has been successfully uploaded. The accounts are currently being checked for validity and integrated into the bot"
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
        "Account integration was successful. \n\nSuccessfully added: {successfully_added} \nTotal processed: {total_processed}"
    ).format(successfully_added=successfully_added, total_processed=total_processed)
    if mark_invalid_acc:
        result_message += get_text(
            user.language,
            "admins_editor_category",
            "\n\nWe couldn't extract the account from some {acc_from}(either the structure is broken or the account is invalid); "
            "they were downloaded as a separate file"
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
            "\n\nSome accounts are already in the bot; they were downloaded as a separate file"
        )
    return result_message
