import shutil
from pathlib import Path

from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message, send_document, send_message
from src.config import get_config
from src.exceptions.business import ForbiddenError
from src.modules.profile.keyboards.purchased_universals_kb import sold_universal_kb, universal_kb
from src.services.database.admins.actions import check_admin
from src.services.database.categories.actions.products.universal.action_delete import delete_sold_universal
from src.services.database.categories.actions.products.universal.action_update import update_universal_storage
from src.services.database.categories.actions.products.universal.actions_add import add_deleted_universal
from src.services.database.categories.actions.products.universal.actions_get import get_sold_universal_by_universal_id
from src.services.database.categories.models import StorageStatus, UniversalMediaType
from src.services.database.categories.models import SoldUniversalFull
from src.services.database.users.models import Users
from src.services.filesystem.actions import create_temp_dir
from src.services.filesystem.universals_products import move_in_universal
from src.services.filesystem.media_paths import create_path_universal_storage
from src.services.secrets import decrypt_text, unwrap_dek, get_crypto_context
from src.services.secrets.decrypt import decrypt_file
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text


async def check_universal_product(
    callback: CallbackQuery,
    user: Users,
    sold_universal_id: int
) -> SoldUniversalFull | None:
    """
    Произведёт поиск универсального товара, если не найдёт, то выведет соответствующие сообщение.
    Проверит что данный товар принадлежит пользователю, если нет, то вызовет ошибку
    """
    universal = await get_sold_universal_by_universal_id(sold_universal_id, language=user.language)
    if not universal:
        await callback.answer(get_text(user.language, "profile_messages", "product_not_found"))

    if universal.owner_id != user.user_id and not await check_admin(user.user_id):
        raise ForbiddenError()

    return universal


async def show_all_sold_universal(
    user_id: int,
    language: str,
    message_id: int,
    current_page: int,
):
    """Отредактирует сообщение и покажет необходимое для аккаунтов по всем сервисам"""
    await edit_message(
        chat_id=user_id,
        message_id=message_id,
        image_key='purchased_universal',
        reply_markup=await sold_universal_kb(
            language=language,
            current_page=current_page,
            user_id=user_id
        )
    )


async def show_sold_universal(
    callback: CallbackQuery,
    universal: SoldUniversalFull,
    language: str,
    current_page: int,
):
    """Отредактирует сообщение и покажет необходимое для универсального продукта"""
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(
            language,
            "profile_messages",
            "universal_product_details"
        ).format(
            product_id=universal.sold_universal_id,
            name=universal.universal_storage.name,
            sold_at=universal.sold_at.strftime(get_config().different.dt_format),
        ),
        image_key='purchased_universal',
        reply_markup=universal_kb(
            language=language,
            sold_universal_id=universal.sold_universal_id,
            current_page=current_page,
        )
    )


async def send_media_sold_universal(
    user_id: int,
    language: str,
    universal: SoldUniversalFull,
):
    """SoldUniversalFull должен быть с переводом для данного пользователя"""
    file_id = None
    decrypted_file_path = None
    description = None

    try:
        crypto = get_crypto_context()

        dek = unwrap_dek(
            encrypted_data_b64=universal.universal_storage.encrypted_key,
            nonce_b64=universal.universal_storage.encrypted_key_nonce,
            kek=crypto.kek,
        )

        if universal.universal_storage.encrypted_tg_file_id:
            file_id = decrypt_text(
                encrypted_data_b64=universal.universal_storage.encrypted_tg_file_id,
                nonce_b64=universal.universal_storage.encrypted_tg_file_id_nonce,
                dek=dek
            )

        if universal.universal_storage.original_filename:
            file_path = create_path_universal_storage(
                status=universal.universal_storage.status,
                uuid=universal.universal_storage.storage_uuid,
            )
            decrypted_file_path = create_temp_dir() / Path(universal.universal_storage.original_filename)
            decrypt_file(
                dek=dek,
                encrypted_path=file_path,
                decrypted_path=str(decrypted_file_path)
            )

        if universal.universal_storage.encrypted_description:
            description = decrypt_text(
                encrypted_data_b64=universal.universal_storage.encrypted_description,
                nonce_b64=universal.universal_storage.encrypted_description_nonce,
                dek=dek
            )

        if file_id or decrypted_file_path:
            await send_document(
                chat_id=user_id,
                file_id=file_id,
                file_path=decrypted_file_path,
                type_based=True if universal.universal_storage.media_type == UniversalMediaType.DOCUMENT else True
            )


        if description:
            await send_message(
                chat_id=user_id,
                message=get_text(
                    language,
                    "profile_messages",
                    "description"
                ).format(description=description),
            )
    except Exception as e:
        get_logger(__name__).exception(f"[send_media_sold_universal] Ошибка выдаче данных о товаре пользователю: {e}")

    if decrypted_file_path:
        shutil.rmtree(decrypted_file_path.parent, ignore_errors=True)


async def delete_sold_universal_han(
    callback: CallbackQuery,
    user: Users,
    universal: SoldUniversalFull,
    current_page: int,
):
    result = await move_in_universal(universal=universal, status=StorageStatus.DELETED)
    if not result:
        await callback.answer(
            get_text(user.language, "miscellaneous", "an_error_occurred"),
            show_alert=True
        )
        return

    await update_universal_storage(
        universal_storage_id=universal.universal_storage_id,
        status=StorageStatus.DELETED,
        is_active=False
    )
    await delete_sold_universal(universal.sold_universal_id)
    await add_deleted_universal(universal_storage_id=universal.universal_storage_id)

    await callback.answer(
        get_text(user.language, "profile_messages", "product_successfully_deleted"),
        show_alert=True
    )

    await show_all_sold_universal(
        user_id=callback.from_user.id,
        language=user.language,
        message_id=callback.message.message_id,
        current_page=current_page,
    )