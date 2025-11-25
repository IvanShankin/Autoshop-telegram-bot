from aiogram.types import CallbackQuery, FSInputFile, BufferedInputFile

from src.bot_actions.actions import send_message
from src.bot_actions.bot_instance import get_bot
from src.exceptions.service_exceptions import ProductAccountNotFound
from src.modules.admin_actions.handlers.editor.category_validator import service_not_found, \
    safe_get_service_name
from src.modules.admin_actions.keyboard_admin import back_in_category_kb
from src.services.accounts.other.upload_account import upload_other_account
from src.services.accounts.tg.upload_account import upload_tg_account
from src.services.database.selling_accounts.models import AccountCategoryFull
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def upload_account(category: AccountCategoryFull, user: Users, callback: CallbackQuery):
    service_name = await safe_get_service_name(category, user, callback.message.message_id)
    bot = await get_bot()

    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins",
            "Account upload has begun. Wait for the message about the completion of the upload"
        )
    )

    try:
        if service_name == "telegram":
            async for archive_path in upload_tg_account(category.account_service_id):
                file = FSInputFile(archive_path)
                await bot.send_document(callback.from_user.id, document=file)
        elif service_name == "other":
            stream_csv = await upload_other_account(category.account_service_id)
            await bot.send_document(
                user.user_id,
                document=BufferedInputFile(
                    stream_csv,
                    filename=get_text(user.language, "admins", "Accounts") + '.csv'
                )
            )
        else:
            await service_not_found(user, callback.message.message_id)
            return
    except ProductAccountNotFound:
        await send_message(user.user_id, get_text(user.language, "admins", "Account not found!"))

    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins",
            "Account upload complete"
        ),
        reply_markup=back_in_category_kb(
            language=user.language,
            category_id=category.account_category_id,
            i18n_key="In category"
        )
    )