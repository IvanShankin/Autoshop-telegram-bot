from aiogram.types import CallbackQuery, FSInputFile, BufferedInputFile

from src.bot_actions.messages import send_message
from src.bot_actions.bot_instance import get_bot
from src.exceptions import ProductAccountNotFound, ProductNotFound
from src.exceptions.business import ServerError
from src.modules.admin_actions.keyboards.editors.category_kb import in_category_kb
from src.modules.admin_actions.services.editor.category.category_loader import service_not_found
from src.modules.admin_actions.keyboards import back_in_category_kb
from src.services.database.categories.models import ProductType, CategoryFull, AccountServiceType
from src.services.products.accounts.other.upload_account import upload_other_account
from src.services.products.accounts.tg.upload_account import upload_tg_account
from src.services.database.users.models import Users
from src.services.products.universals.upload_products import upload_universal_products
from src.utils.i18n import get_text

async def complete_upload(category: CategoryFull, user: Users):
    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins_editor_category",
            "products_upload_complete"
        ),
        reply_markup=in_category_kb(
            language=user.language,
            category_id=category.category_id
        )
    )


async def _upload_account(category: CategoryFull, user: Users, callback: CallbackQuery):
    bot = await get_bot()

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
                    filename=get_text(user.language, "admins_editor_category", "accounts") + '.csv'
                )
            )
        else:
            await service_not_found(user, callback.message.message_id)
            return
    except ProductAccountNotFound:
        await send_message(user.user_id, get_text(user.language, "admins_editor_category", "products_not_found"))
    except ServerError:
        await send_message(user.user_id, get_text(user.language, "miscellaneous", "server_error"))

    await complete_upload(category, user)


async def _upload_universal(category: CategoryFull, user: Users, callback: CallbackQuery):
    bot = await get_bot()

    try:
        gen = upload_universal_products(category)
        archive_path = await anext(gen)

        file = FSInputFile(archive_path)
        await bot.send_document(callback.from_user.id, document=file)

        await anext(gen) # удаление
    except ProductNotFound:
        await send_message(user.user_id, get_text(user.language, "admins_editor_category", "products_not_found"))

    await complete_upload(category, user)


async def upload_category(category: CategoryFull, user: Users, callback: CallbackQuery):
    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins_editor_category",
            "account_upload_begun"
        )
    )

    if category.product_type == ProductType.ACCOUNT:
        await _upload_account(category, user, callback)
    elif category.product_type == ProductType.UNIVERSAL:
        await _upload_universal(category, user, callback)