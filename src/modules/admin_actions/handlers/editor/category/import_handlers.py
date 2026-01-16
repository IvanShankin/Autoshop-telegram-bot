import io
import os
from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile, BufferedInputFile

from src.bot_actions.messages import edit_message, send_message, send_log
from src.bot_actions.bot_instance import get_bot
from src.config import get_config
from src.exceptions import TypeAccountServiceNotFound, InvalidFormatRows
from src.modules.admin_actions.keyboards import back_in_category_kb, \
    name_or_description_kb
from src.modules.admin_actions.schemas import ImportAccountsData
from src.modules.admin_actions.services import safe_get_category, service_not_found
from src.modules.admin_actions.services import message_info_load_file, make_result_msg
from src.modules.admin_actions.services import check_valid_file, check_category_is_acc_storage
from src.modules.admin_actions.state import ImportTgAccounts, ImportOtherAccounts
from src.services.accounts.other.input_account import input_other_account
from src.services.accounts.tg.input_account import import_telegram_accounts_from_archive
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.users.models import Users
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data.startswith("category_load_products:"))
async def category_load_products(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    category = await safe_get_category(category_id, user=user, callback=None)
    if not category:
        return

    if category.type_account_service == AccountServiceType.TELEGRAM:
        await edit_message(
            chat_id=user.user_id,
            message_id=callback.message.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "Send the archive with the exact folder and archive structure as shown in the photo"
            ),
            image_key="info_add_accounts",
            reply_markup=back_in_category_kb(user.language, category_id)
        )
        await state.set_state(ImportTgAccounts.archive)
        await state.update_data(category_id=category_id, type_account_service=category.type_account_service)
    elif category.type_account_service == AccountServiceType.OTHER:
        await edit_message(
            chat_id=user.user_id,
            message_id=callback.message.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "Send a file with the '.csv' extension.\n\n"
                "It must have the structure shown in the photo.\n"
                "Please pay attention to the headers; they must be strictly followed!\n\n"
                "Required Headers (can be copied):\n'<code>phone</code>', '<code>login</code>', '<code>password</code>'\n\n"
                "Note: To create a '.csv' file, create an exal workbook and save it as '.csv'"
            ),
            image_key="example_csv",
            reply_markup=back_in_category_kb(user.language, category_id)
        )
        await state.set_state(ImportOtherAccounts.csv_file)
        await state.update_data(category_id=category_id, type_account_service=category.type_account_service)
    else:
        await service_not_found(user, callback.message.message_id)


@router.callback_query(F.data.startswith("choice_lang_category_data:"))
async def choice_lang_category_data(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    lang = callback.data.split(':')[2]

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_category",
            "Select the desired section"
        ),
        reply_markup=name_or_description_kb(user.language, category_id, lang)
    )


@router.message(ImportTgAccounts.archive, F.document)
async def import_tg_account(message: Message, state: FSMContext, user: Users):
    async def load_file(file_path: str, caption: str):
        try:
            message_loading = await send_message(
                message.from_user.id, get_text(user.language, "miscellaneous", "File loading")
            )
            bot = await get_bot()
            file = FSInputFile(file_path)
            await bot.send_document(message.from_user.id, document=file, caption=caption)
            await message_loading.delete()
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"[import_tg_account.load_file] - ошибка: '{str(e)}'")
            pass


    data = ImportAccountsData(**(await state.get_data()))
    category = await safe_get_category(data.category_id, user=user, callback=None)
    if not category:
        return

    await check_category_is_acc_storage(category, user)

    doc = message.document
    valid_file = await check_valid_file(
        doc=doc,
        user=user,
        state=state,
        expected_formats=get_config().app.supported_archive_extensions,
        set_state=ImportTgAccounts.archive
    )
    if not valid_file:
        return


    save_path = str(Path(get_config().paths.temp_file_dir) / doc.file_name)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file = await message.bot.get_file(doc.file_id) # Получаем объект файла

    gen_mes_info = message_info_load_file(user)
    await gen_mes_info.__anext__()
    await message.bot.download_file(file.file_path, destination=save_path) # Скачиваем файл на диск
    message_info = await gen_mes_info.__anext__()

    try:
        gen_import_acc = import_telegram_accounts_from_archive(
            archive_path=save_path,
            category_id=data.category_id,
            type_account_service=data.type_account_service
        )
        result = await gen_import_acc.__anext__()

        result_message = make_result_msg(
            user=user,
            successfully_added=result.successfully_added,
            total_processed=result.total_processed,
            mark_invalid_acc=result.invalid_archive_path,
            mark_duplicate_acc=result.duplicate_archive_path,
            tg_acc=True
        )

        await edit_message(
            message.from_user.id,
            message_info.message_id,
            result_message,
            reply_markup=back_in_category_kb(user.language, data.category_id, i18n_key="In category")
        )

        if result.invalid_archive_path:
            await load_file(
                result.invalid_archive_path,
                caption=get_text(user.language,"admins_editor_category", "Failed account extraction")
            )

        if result.duplicate_archive_path:
            await load_file(
                result.duplicate_archive_path,
                caption=get_text(user.language, "admins_editor_category", "Duplicate accounts")
            )

    except TypeAccountServiceNotFound:
        await service_not_found(user)
    except Exception as e:
        text = f"#Ошибка_при_добавлении_аккаунтов  [import_tg_account]. \nОшибка='{str(e)}'"
        logger = get_logger(__name__)
        logger.exception(text)
        await send_log(text)
        await send_message(
            message.from_user.id,
            get_text(user.language,"admins_editor_category", "An error occurred inside the server, see the logs!")
        )


@router.message(ImportOtherAccounts.csv_file, F.document)
async def import_other_account(message: Message, state: FSMContext, user: Users):
    data = ImportAccountsData(**(await state.get_data()))
    category = await safe_get_category(data.category_id, user=user, callback=None)
    if not category:
        return

    await check_category_is_acc_storage(category, user)

    doc = message.document
    valid_file = await check_valid_file(
        doc=doc,
        user=user,
        state=state,
        expected_formats=["csv"],
        set_state=ImportOtherAccounts.csv_file
    )
    if not valid_file:
        return


    gen_mes_info = message_info_load_file(user)
    await gen_mes_info.__anext__()

    file = await message.bot.get_file(doc.file_id)
    stream = io.BytesIO()
    await message.bot.download_file(file.file_path, stream)
    stream.seek(0)

    message_info = await gen_mes_info.__anext__()

    try:
        result = await input_other_account(stream, data.category_id, data.type_account_service)
        result_message = make_result_msg(
            user=user,
            successfully_added=result.successfully_added,
            total_processed=result.total_processed,
            mark_invalid_acc=result.errors_csv_bytes,
            mark_duplicate_acc=result.duplicates_csv_bytes
        )
        await edit_message(
            message.from_user.id,
            message_info.message_id,
            result_message,
            reply_markup=back_in_category_kb(user.language, data.category_id, i18n_key="In category")
        )
        if result.errors_csv_bytes:
            await message.answer_document(
                BufferedInputFile(
                    result.errors_csv_bytes,
                    filename=get_text(user.language,"admins_editor_category", "Failed account extraction") + '.csv'
                )
            )
        if result.duplicates_csv_bytes:
            await message.answer_document(
                BufferedInputFile(
                    result.duplicates_csv_bytes,
                    filename=get_text(user.language, "admins_editor_category", "Duplicate accounts") + '.csv'
                )
            )

    except InvalidFormatRows:
        await edit_message(
            chat_id=user.user_id,
            message_id=message_info.message_id,
            message=get_text(
                user.language,
                "admins_editor_category",
                "The resulting file has incorrect header formatting. \n"
            "Carefully examine the attached photo and try again \n\n"
            "Required Headers (can be copied):\n'<code>phone</code>', '<code>login</code>', '<code>password</code>'"
            ),
            image_key="example_csv",
            reply_markup=back_in_category_kb(user.language, data.category_id, i18n_key="In category")
        )
        await state.set_state(ImportOtherAccounts.csv_file)
    except TypeAccountServiceNotFound:
        await service_not_found(user)
    except Exception as e:
        text = f"#Ошибка_при_добавлении_аккаунтов  [import_other_account]. \nОшибка='{str(e)}'"
        logger = get_logger(__name__)
        logger.exception(text)
        await send_log(text)
        await send_message(
            message.from_user.id,
            get_text(user.language,"admins_editor_category", "An error occurred inside the server, see the logs!")
        )