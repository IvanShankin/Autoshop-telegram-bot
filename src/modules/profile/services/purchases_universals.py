import shutil
from pathlib import Path

from aiogram.types import CallbackQuery

from src.application._secrets.crypto_context import get_crypto_context
from src.config import get_config
from src.domain.crypto.key_ops import unwrap_dek
from src.models.create_models.universal import CreateDeletedUniversalDTO
from src.models.update_models import UpdateUniversalStorageDTO
from src.modules.profile.keyboards.purchased_universals_kb import sold_universal_kb
from src.database.models.categories import StorageStatus, UniversalMediaType
from src.models.read_models import SoldUniversalFull, UsersDTO
from src.application.bot import Messages
from src.infrastructure.files.file_system import create_temp_dir
from src.application.products.universals.universals_products import move_in_universal
from src.infrastructure.files._media_paths import create_path_universal_storage
from src.application.models.modules import ProfileModule
from src.domain.crypto.decrypt import decrypt_file, decrypt_text
from src.utils.i18n import get_text


async def check_universal_product(
    callback: CallbackQuery,
    user: UsersDTO,
    sold_universal_id: int,
    profile_module: ProfileModule,
) -> SoldUniversalFull | None:
    """
    Произведёт поиск универсального товара, если не найдёт, то выведет соответствующие сообщение.
    Проверит что данный товар принадлежит пользователю, если нет, то вызовет ошибку
    """
    universal = await profile_module.universal_moduls.sold_service.get_sold_universal_by_universal_id(
        sold_universal_id=sold_universal_id, language=user.language
    )
    if not universal:
        await callback.answer(get_text(user.language, "profile_messages", "product_not_found"))

    await profile_module.permission_service.check_permission(user.user_id, universal.owner_id)

    return universal


async def show_all_sold_universal(
    user: UsersDTO,
    message_id: int,
    current_page: int,
    messages_service: Messages,
    profile_module: ProfileModule,
):
    """Отредактирует сообщение и покажет необходимое для аккаунтов по всем сервисам"""
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=message_id,
        event_message_key='purchased_universal',
        reply_markup=await sold_universal_kb(
            language=user.language,
            current_page=current_page,
            user_id=user.user_id,
            profile_module=profile_module
        )
    )


async def send_media_sold_universal(
    user_id: int,
    language: str,
    universal: SoldUniversalFull,
    messages_service: Messages,
    profile_module: ProfileModule,
):
    """SoldUniversalFull должен быть с переводом для данного пользователя"""
    file_id = None
    decrypted_file_path = None
    description = None

    try:
        crypto = profile_module.crypto_provider.get()

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
            decrypted_file_path = create_temp_dir(get_config()) / Path(universal.universal_storage.original_filename)
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
            await messages_service.send_file.send_document(
                chat_id=user_id,
                file_id=file_id,
                file_path=decrypted_file_path,
                type_based=False if universal.universal_storage.media_type == UniversalMediaType.DOCUMENT else True
            )


        if description:
            await messages_service.send_msg.send(
                chat_id=user_id,
                message=get_text(
                    language,
                    "profile_messages",
                    "description"
                ).format(description=description),
            )
    except Exception as e:
        profile_module.logger.exception(f"[send_media_sold_universal] Ошибка выдаче данных о товаре пользователю: {e}")

    if decrypted_file_path:
        shutil.rmtree(decrypted_file_path.parent, ignore_errors=True)


async def delete_sold_universal_han(
    callback: CallbackQuery,
    user: UsersDTO,
    universal: SoldUniversalFull,
    current_page: int,
    messages_service: Messages,
    profile_module: ProfileModule,
):
    result = await move_in_universal(universal=universal, status=StorageStatus.DELETED)
    if not result:
        await callback.answer(
            get_text(user.language, "miscellaneous", "an_error_occurred"),
            show_alert=True
        )
        return

    await profile_module.universal_moduls.storage_service.update_universal_storage(
        universal_storage_id=universal.universal_storage_id,
        data=UpdateUniversalStorageDTO(
            status=StorageStatus.DELETED,
            is_active=False,
        )
    )
    await profile_module.universal_moduls.sold_service.delete_sold_universal(
        universal.sold_universal_id,
    )
    await profile_module.universal_moduls.deleted_service.create_deleted_universal(
        data=CreateDeletedUniversalDTO(
            universal_storage_id=universal.universal_storage_id
        ),
    )

    await callback.answer(
        get_text(user.language, "profile_messages", "product_successfully_deleted"),
        show_alert=True
    )

    await show_all_sold_universal(
        user=user,
        message_id=callback.message.message_id,
        current_page=current_page,
        messages_service=messages_service,
        profile_module=profile_module,
    )