from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.infrastructure.telegram.bot_client import TelegramClient
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import admin_settings_kb
from src.modules.admin_actions.keyboards.settings_kb import confirm_overwrite_cache_kb, back_in_admin_settings_kb
from src.infrastructure.files.file_system import split_file_on_chunk
from src.utils.i18n import get_text

router = Router()
router_logger = Router()


async def send_log_files(
    messages_service: Messages,
    chat_id: int,
    language: str,
    admin_module: AdminModule,
    tg_client: TelegramClient
):
    await messages_service.send_msg.send(
        chat_id=chat_id,
        message=get_text(language, "admins_settings", "log_upload_begun")
    )

    async for chunk_path in split_file_on_chunk(admin_module.conf.paths.log_file, admin_module.conf):
        await tg_client.send_document(
            chat_id=chat_id,
            document=FSInputFile(chunk_path)
        )

    await messages_service.send_msg.send(
        chat_id=chat_id,
        message=get_text(language, "admins_settings", "log_upload_complete")
    )


@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    await state.clear()
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=admin_settings_kb(user.language)
    )


@router.callback_query(F.data == "download_logs")
async def download_logs(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    await send_log_files(messages_service, user.user_id, user.language, admin_module, tg_client)


@router.callback_query(F.data == "confirm_overwrite_cache")
async def overwrite_cache(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message=get_text(user.language, "admins_settings", "confirm_overwrite_cache"),
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=confirm_overwrite_cache_kb(user.language)
    )


@router.callback_query(F.data == "overwrite_cache")
async def overwrite_cache(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule):
    settings = await admin_module.settings_service.get_settings()

    if not settings.maintenance_mode:
        message = get_text(user.language, "admins_settings", "first_on_mode_maintenance_work")
    else:
        await admin_module.cache_warmup_service.warmup()
        message = get_text(user.language, "admins_settings", "overwrite_cache_complete")
        await admin_module.publish_event_handler.send_log(text=f"admin_id: {user.user_id}\n\nАдмин перезаписал кеш.")

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message=message,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=back_in_admin_settings_kb(user.language)
    )


@router_logger.message(Command("get_log"))
async def cmd_start(
    message: Message,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_logger_client: TelegramClient,
):
    settings = await admin_module.settings_service.get_settings()
    if await admin_module.admin_service.check_admin(user.user_id) or settings.channel_for_logging_id == message.chat.id:
        await send_log_files(
            messages_service, message.chat.id, admin_module.conf.app.default_lang, admin_module, tg_logger_client
        )