from aiogram.types import CallbackQuery, FSInputFile, BufferedInputFile

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.exceptions import ProductAccountNotFound, ProductNotFound
from src.exceptions.business import ServerError
from src.infrastructure.telegram.bot_client import TelegramClient
from src.modules.admin_actions.keyboards.editors.category_kb import in_category_kb
from src.modules.admin_actions.services.editor.category.category_loader import service_not_found
from src.database.models.categories import ProductType, AccountServiceType
from src.models.read_models import CategoryFull, UsersDTO
from src.utils.i18n import get_text


async def complete_upload(category: CategoryFull, user: UsersDTO, messages_service: Messages,):
    await messages_service.send_msg.send(
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


async def _upload_account(
    category: CategoryFull,
    user: UsersDTO,
    callback: CallbackQuery,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    try:
        if category.type_account_service == AccountServiceType.TELEGRAM:
            async for archive_path in admin_module.upload_tg_account_use_case.execute(category.category_id):
                file = FSInputFile(archive_path)
                await tg_client.send_document(callback.from_user.id, document=file)

        elif category.type_account_service == AccountServiceType.OTHER:
            stream_csv = await admin_module.upload_other_account_use_case.execute(category.category_id)
            await tg_client.send_document(
                user.user_id,
                document=BufferedInputFile(
                    stream_csv,
                    filename=get_text(user.language, "admins_editor_category", "accounts") + '.csv'
                )
            )

        else:
            await service_not_found(
                user=user,
                messages_service=messages_service,
                tg_client=tg_client,
                message_id_delete=callback.message.message_id,
            )
            return

    except ProductAccountNotFound:
        await messages_service.send_msg.send(user.user_id, get_text(user.language, "admins_editor_category", "products_not_found"))

    except ServerError:
        await messages_service.send_msg.send(user.user_id, get_text(user.language, "miscellaneous", "server_error"))

    await complete_upload(category, user, messages_service)


async def _upload_universal(
    category: CategoryFull,
    user: UsersDTO,
    callback: CallbackQuery,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    try:
        gen = admin_module.upload_universal_products_use_case.execute(category)
        archive_path = await anext(gen)

        file = FSInputFile(archive_path)
        await tg_client.send_document(callback.from_user.id, document=file)

        await anext(gen) # удаление
    except ProductNotFound:
        await messages_service.send_msg.send(user.user_id, get_text(user.language, "admins_editor_category", "products_not_found"))

    await complete_upload(category, user, messages_service)


async def upload_category(
    category: CategoryFull,
    user: UsersDTO,
    callback: CallbackQuery,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    await messages_service.send_msg.send(
        user.user_id,
        get_text(
            user.language,
            "admins_editor_category",
            "account_upload_begun"
        )
    )

    if category.product_type == ProductType.ACCOUNT:
        await _upload_account(
            category=category,
            user=user,
            callback=callback,
            admin_module=admin_module,
            messages_service=messages_service,
            tg_client=tg_client,
        )
    elif category.product_type == ProductType.UNIVERSAL:
        await _upload_universal(
            category=category,
            user=user,
            callback=callback,
            admin_module=admin_module,
            messages_service=messages_service,
            tg_client=tg_client,
        )