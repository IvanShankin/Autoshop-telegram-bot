from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from src.bot_actions.bot_instance import get_bot, get_bot_logger
from src.bot_actions.messages import edit_message
from src.config import get_config
from src.modules.admin_actions.keyboards import admin_settings_kb
from src.services.database.admins.actions import check_admin
from src.services.database.system.actions import get_settings
from src.services.database.users.models import Users
from src.services.filesystem.actions import split_file_on_chunk
from src.utils.i18n import get_text

router = Router()
router_logger = Router()


async def send_log_files(bot: Bot, chat_id: int, language: str):
    await bot.send_message(
        chat_id=chat_id,
        text=get_text(language, "admins_settings", "log_upload_begun")
    )

    async for chunk_path in split_file_on_chunk(get_config().paths.log_file):
        await bot.send_document(chat_id,FSInputFile(chunk_path))

    await bot.send_message(
        chat_id=chat_id,
        text=get_text(language, "admins_settings", "log_upload_complete")
    )


@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=admin_settings_kb(user.language)
    )


@router.callback_query(F.data == "download_logs")
async def download_logs(callback: CallbackQuery, state: FSMContext, user: Users):
    bot = await get_bot()
    await send_log_files(bot, user.user_id, user.language)


@router_logger.message(Command("get_log"))
async def cmd_start(message: Message, user: Users):
    settings = await get_settings()
    bot_logger = await get_bot_logger()
    if await check_admin(user.user_id) or settings.channel_for_logging_id == message.chat.id:
        await send_log_files(bot_logger, message.chat.id, get_config().app.default_lang)