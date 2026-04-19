import asyncio
import io
import os
from pathlib import Path
from typing import Callable, Any

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile, BufferedInputFile

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.application.products.universals.dto import get_import_universal_headers
from src.infrastructure.telegram.bot_client import TelegramClient
from src.models.read_models import UsersDTO
from src.exceptions import TypeAccountServiceNotFound, InvalidFormatRows
from src.exceptions.business import ImportUniversalInvalidMediaData, ImportUniversalFileNotFound, \
    CsvHasMoreThanTwoProducts
from src.modules.admin_actions.keyboards import name_or_description_kb
from src.modules.admin_actions.keyboards.editors.category_kb import get_example_import_product_kb, \
    get_example_import_other_acc_kb, get_example_import_tg_acc_kb, in_category_kb, get_logs_and_back_in_category_kb
from src.modules.admin_actions.schemas import ImportAccountsData
from src.modules.admin_actions.schemas.editors.editor_categories import ImportUniversalsData
from src.modules.admin_actions.services import safe_get_category, service_not_found
from src.modules.admin_actions.services import message_info_load_file, make_result_msg
from src.modules.admin_actions.services import check_valid_file, check_category_is_acc_storage
from src.modules.admin_actions.state import ImportTgAccounts, ImportOtherAccounts
from src.modules.admin_actions.state.editors.editor_categories import ImportUniversalProducts
from src.database.models.categories import ProductType
from src.infrastructure.files.file_system import create_temp_dir
from src.database.models.categories import AccountServiceType
from src.utils.helpers_func import maybe_await
from src.infrastructure.translations import get_text

router = Router()


async def _send_example(file_key: str, user_id: int, func_generate: Callable[[], Any], messages_service: Messages,):
    try:
        await messages_service.send_file.send_file_by_file_key(
            chat_id=user_id,
            file_key=file_key,
        )
    except FileNotFoundError:
        await maybe_await(func_generate())
        await messages_service.send_file.send_file_by_file_key(
            chat_id=user_id,
            file_key=file_key,
        )


@router.callback_query(F.data.startswith("category_load_products:"))
async def category_load_products(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    messages_service: Messages,
    admin_module: AdminModule,
    tg_client: TelegramClient,
):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(
        category_id, user=user, callback=None, admin_module=admin_module, messages_service=messages_service
    )
    if not category:
        return

    if category.product_type == ProductType.ACCOUNT:
        if category.type_account_service == AccountServiceType.TELEGRAM:
            await messages_service.edit_msg.edit(
                chat_id=user.user_id,
                message_id=callback.message.message_id,
                message=get_text(
                    user.language,
                    "admins_editor_category",
                    "send_archive_with_the_folder_structure_as_shown_in_the_photo"
                ),
                event_message_key="info_add_accounts",
                reply_markup=get_example_import_tg_acc_kb(user.language, category_id)
            )
            await state.set_state(ImportTgAccounts.archive)
            await state.update_data(category_id=category_id, type_account_service=category.type_account_service)

        elif category.type_account_service == AccountServiceType.OTHER:
            await messages_service.edit_msg.edit(
                chat_id=user.user_id,
                message_id=callback.message.message_id,
                message=get_text(
                    user.language,
                    "admins_editor_category",
                    "description_csv_file_for_import_other_account"
                ),
                event_message_key="example_csv",
                reply_markup=get_example_import_other_acc_kb(user.language, category_id)
            )
            await state.set_state(ImportOtherAccounts.csv_file)
            await state.update_data(category_id=category_id, type_account_service=category.type_account_service)

        else:
            await service_not_found(
                user,
                messages_service=messages_service,
                tg_client=tg_client,
                message_id_delete=callback.message.message_id,
            )

    elif category.product_type == ProductType.UNIVERSAL:
        headers_csv = [f"<code>{head}</code>" for head in get_import_universal_headers(conf=admin_module.conf)]
        await messages_service.edit_msg.edit(
            chat_id=user.user_id,
            message_id=callback.message.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "universal_products_import_instructions"
            ).format(
                headers_csv=str(headers_csv),
                media_type=str(category.media_type.name),
                info_reuse_product=get_text(
                    user.language,
                "admins_editor_category",
                "info_reuse_product"
                ) if category.reuse_product else ""
            ),
            reply_markup=get_example_import_product_kb(user.language, category_id)
        )
        await state.set_state(ImportUniversalProducts.archive)
        await state.update_data(category_id=category_id)


@router.callback_query(F.data == "get_example_import_tg_acc")
async def get_example_import_tg_acc(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages
):
    await _send_example(
        file_key=admin_module.conf.file_keys.example_zip_for_import_tg_acc_key.key,
        user_id=user.user_id,
        func_generate=admin_module.generate_example_import_account.generate_example_import_tg_acc,
        messages_service=messages_service,
    )


@router.callback_query(F.data == "get_example_import_other_acc")
async def get_example_import_other_acc(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages
):
    await _send_example(
        file_key=admin_module.conf.file_keys.example_csv_for_import_other_acc_key.key,
        user_id=user.user_id,
        func_generate=admin_module.generate_example_import_account.generate_example_import_other_acc,
        messages_service=messages_service,
    )


@router.callback_query(F.data == "get_example_import_universals")
async def get_example_import_universals(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages
):
    await _send_example(
        file_key=admin_module.conf.file_keys.example_zip_for_universal_import_key.key,
        user_id=user.user_id,
        func_generate=admin_module.generate_exampl_universal_import.generate,
        messages_service=messages_service,
    )


@router.callback_query(F.data.startswith("choice_lang_category_data:"))
async def choice_lang_category_data(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages
):
    category_id = int(callback.data.split(':')[1])
    lang = callback.data.split(':')[2]

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "select_desired_section"
        ),
        reply_markup=name_or_description_kb(user.language, category_id, lang)
    )


@router.message(ImportTgAccounts.archive, F.document)
async def import_tg_account(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    async def load_file(file_path: str, caption: str):
        try:
            message_loading = await messages_service.send_msg.send(
                message.from_user.id, get_text(user.language, "miscellaneous", "file_loading")
            )
            file = FSInputFile(file_path)

            await tg_client.send_document(message.from_user.id, document=file, caption=caption)
            await message_loading.delete()

        except Exception as e:
            admin_module.logger.warning(f"[import_tg_account.load_file] - ошибка: '{str(e)}'")
            pass


    data = ImportAccountsData(**(await state.get_data()))
    category = await safe_get_category(
        data.category_id, user=user, callback=None, admin_module=admin_module, messages_service=messages_service,
    )
    if not category:
        return

    await check_category_is_acc_storage(category, user, messages_service=messages_service)

    doc = message.document
    valid_file = await check_valid_file(
        doc=doc,
        user=user,
        state=state,
        expected_formats=admin_module.conf.app.supported_archive_extensions,
        set_state=ImportTgAccounts.archive,
        admin_module=admin_module,
        messages_service=messages_service,
    )
    if not valid_file:
        return

    save_path = str(create_temp_dir(admin_module.conf) / doc.file_name)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file = await message.bot.get_file(doc.file_id) # Получаем объект файла

    gen_mes_info = message_info_load_file(user, messages_service=messages_service,)
    await gen_mes_info.__anext__()

    try:
        await message.bot.download_file(file.file_path, destination=save_path) # Скачиваем файл на диск
    except asyncio.TimeoutError:
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "error_downloading_file_to_server"
            )
        )
        return

    message_info = await gen_mes_info.__anext__()

    gen_import_acc = admin_module.import_tg_account.import_telegram_accounts_from_archive(
        archive_path=save_path,
        category_id=data.category_id,
        type_account_service=data.type_account_service
    )
    try:
        result = await gen_import_acc.__anext__()

        result_message = make_result_msg(
            user=user,
            successfully_added=result.successfully_added,
            total_processed=result.total_processed,
            mark_invalid_acc=result.invalid_archive_path,
            mark_duplicate_acc=result.duplicate_archive_path,
            tg_acc=True
        )

        await messages_service.edit_msg.edit(
            message.from_user.id,
            message_info.message_id,
            result_message,
            reply_markup=in_category_kb(user.language, data.category_id)
        )

        if result.invalid_archive_path:
            await load_file(
                result.invalid_archive_path,
                caption=get_text(user.language,"admins_editor_category", "failed_account_extraction")
            )

        if result.duplicate_archive_path:
            await load_file(
                result.duplicate_archive_path,
                caption=get_text(user.language, "admins_editor_category", "Duplicate accounts")
            )

    except TypeAccountServiceNotFound:
        await service_not_found(user, messages_service=messages_service, tg_client=tg_client)
    except Exception as e:
        text = f"#Ошибка_при_добавлении_аккаунтов  [import_tg_account]. \nОшибка='{str(e)}'"

        await admin_module.publish_event_handler.send_log(text=text)

        await messages_service.send_msg.send(
            message.from_user.id,
            get_text(user.language,"admins_editor_category", "error_inside_server"),
            reply_markup=get_logs_and_back_in_category_kb(language=user.language, category_id=data.category_id)
        )

    await gen_import_acc.__anext__() # удаление временных файлов


@router.message(ImportOtherAccounts.csv_file, F.document)
async def import_other_account(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    data = ImportAccountsData(**(await state.get_data()))
    category = await safe_get_category(
        data.category_id, user=user, callback=None, admin_module=admin_module, messages_service=messages_service
    )
    if not category:
        return

    await check_category_is_acc_storage(category, user, messages_service=messages_service)

    doc = message.document
    valid_file = await check_valid_file(
        doc=doc,
        user=user,
        state=state,
        expected_formats=["csv"],
        set_state=ImportOtherAccounts.csv_file,
        admin_module=admin_module,
        messages_service=messages_service,
    )
    if not valid_file:
        return


    gen_mes_info = message_info_load_file(user, messages_service=messages_service,)
    await gen_mes_info.__anext__()

    file = await message.bot.get_file(doc.file_id)
    stream = io.BytesIO()
    await message.bot.download_file(file.file_path, stream)
    stream.seek(0)

    message_info = await gen_mes_info.__anext__()

    try:
        result = await admin_module.import_other_account.execute(stream, data.category_id, data.type_account_service)
        result_message = make_result_msg(
            user=user,
            successfully_added=result.successfully_added,
            total_processed=result.total_processed,
            mark_invalid_acc=result.errors_csv_bytes,
            mark_duplicate_acc=result.duplicates_csv_bytes
        )
        await messages_service.edit_msg.edit(
            message.from_user.id,
            message_info.message_id,
            result_message,
            reply_markup=in_category_kb(user.language, data.category_id)
        )
        if result.errors_csv_bytes:
            await message.answer_document(
                BufferedInputFile(
                    result.errors_csv_bytes,
                    filename=get_text(user.language,"admins_editor_category", "failed_account_extraction") + '.csv'
                )
            )
        if result.duplicates_csv_bytes:
            await message.answer_document(
                BufferedInputFile(
                    result.duplicates_csv_bytes,
                    filename=get_text(user.language, "admins_editor_category", "duplicate_accounts") + '.csv'
                )
            )

    except InvalidFormatRows:
        await messages_service.edit_msg.edit(
            chat_id=user.user_id,
            message_id=message_info.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "incorrect_header_formatting_for_import_other_account"
            ),
            event_message_key="example_csv",
            reply_markup=in_category_kb(user.language, data.category_id)
        )
        await state.set_state(ImportOtherAccounts.csv_file)
    except TypeAccountServiceNotFound:
        await service_not_found(user, messages_service=messages_service, tg_client=tg_client)
    except Exception as e:
        text = f"#Ошибка_при_добавлении_аккаунтов  [import_other_account]. \nОшибка='{str(e)}'"
        await admin_module.publish_event_handler.send_log(text=text)

        await messages_service.send_msg.send(
            message.from_user.id,
            get_text(user.language,"admins_editor_category", "error_inside_server"),
            reply_markup=get_logs_and_back_in_category_kb(language=user.language, category_id=data.category_id)
        )


@router.message(ImportUniversalProducts.archive, F.document)
async def import_universal_products(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    data = ImportUniversalsData(**(await state.get_data()))
    category = await safe_get_category(
        data.category_id, user=user, callback=None, admin_module=admin_module, messages_service=messages_service
    )
    if not category:
        return

    await check_category_is_acc_storage(category, user, messages_service)

    doc = message.document
    valid_file = await check_valid_file(
        doc=doc,
        user=user,
        state=state,
        expected_formats=["zip"],
        set_state=ImportUniversalProducts.archive,
        admin_module=admin_module,
        messages_service=messages_service,
    )
    if not valid_file:
        return

    gen_mes_info = message_info_load_file(user, messages_service=messages_service)
    await gen_mes_info.__anext__()

    temp_dir = create_temp_dir(admin_module.conf)
    archive_path = Path(temp_dir) / doc.file_name

    file = await message.bot.get_file(doc.file_id)
    await message.bot.download_file(
        file_path=file.file_path,
        destination=archive_path
    )

    if not archive_path.exists() or archive_path.stat().st_size == 0:
        raise InvalidFormatRows("Не удалось скачать архив")

    message_info = await gen_mes_info.__anext__()

    try:
        total_added = await admin_module.import_universal_product.execute(
            path_to_archive=archive_path,
            media_type=category.media_type,
            category_id=category.category_id,
            only_one=True if category.reuse_product else False
        )
        await messages_service.edit_msg.edit(
            chat_id=user.user_id,
            message_id=message_info.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "products_integration_was_successful"
            ).format(successfully_added=total_added, total_processed=total_added),
            reply_markup=in_category_kb(user.language, data.category_id)
        )

    except ImportUniversalFileNotFound as e:
        await messages_service.edit_msg.edit(
            chat_id=user.user_id,
            message_id=message_info.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "error_import_universal_file_not_found"
            ).format(file_name=e.file_name),
            reply_markup=in_category_kb(user.language, data.category_id)
        )
        await state.set_state(ImportUniversalProducts.archive)
    except ImportUniversalInvalidMediaData:
        await messages_service.edit_msg.edit(
            chat_id=user.user_id,
            message_id=message_info.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "error_import_universal_media_type"
            ).format(media_type=str(category.media_type.name)),
            reply_markup=in_category_kb(user.language, data.category_id)
        )
        await state.set_state(ImportUniversalProducts.archive)
    except CsvHasMoreThanTwoProducts:
        await messages_service.edit_msg.edit(
            chat_id=user.user_id,
            message_id=message_info.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "error_import_universal_has_more_two"
            ).format(media_type=str(category.media_type.name)),
            reply_markup=in_category_kb(user.language, data.category_id)
        )
        await state.set_state(ImportUniversalProducts.archive)
    except Exception as e:
        text = f"#Ошибка_при_добавлении_товара  [import_universal_products]. \nОшибка='{str(e)}'"
        await admin_module.publish_event_handler.send_log(text=text)

        await messages_service.send_msg.send(
            message.from_user.id,
            get_text(user.language,"admins_editor_category", "error_inside_server"),
            reply_markup=get_logs_and_back_in_category_kb(language=user.language, category_id=data.category_id)
        )