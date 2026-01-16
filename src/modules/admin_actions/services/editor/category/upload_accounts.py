from aiogram.types import CallbackQuery, FSInputFile, BufferedInputFile

from src.bot_actions.messages import send_message
from src.bot_actions.bot_instance import get_bot
from src.exceptions import ProductAccountNotFound
from src.modules.admin_actions.services.editor.category.category_loader import service_not_found
from src.modules.admin_actions.keyboards import back_in_category_kb
from src.services.accounts.other.upload_account import upload_other_account
from src.services.accounts.tg.upload_account import upload_tg_account
from src.services.database.categories.models import CategoryFull
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def upload_account(category: CategoryFull, user: Users, callback: CallbackQuery):
    bot = await get_bot()

    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins_editor_category",
            "Account upload has begun. Wait for the message about the completion of the upload"
        )
    )

    try:
        if category.type_account_service == AccountServiceType.TELEGRAM:
            async for archive_path in upload_tg_account(category.category_id):
                file = FSInputFile(archive_path)
                await bot.send_document(callback.from_user.id, document=file)
        elif category.type_account_service == AccountServiceType.OTHER:
            stream_csv = await upload_other_account(category.category_id)
            await bot.send_document(
                user.user_id,
                document=BufferedInputFile(
                    stream_csv,
                    filename=get_text(user.language, "admins_editor_category", "Accounts") + '.csv'
                )
            )
        else:
            await service_not_found(user, callback.message.message_id)
            return
    except ProductAccountNotFound:
        await send_message(user.user_id, get_text(user.language, "admins_editor_category", "Account not found!"))

    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins_editor_category",
            "Account upload complete"
        ),
        reply_markup=back_in_category_kb(
            language=user.language,
            category_id=category.category_id,
            i18n_key="In category"
        )
    )