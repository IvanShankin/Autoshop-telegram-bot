from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot_actions.actions import send_message
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.catalog.keyboard_catalog import catalog_kb
from src.services.database.system.actions import get_settings
from src.services.database.users.actions import get_user
from src.utils.i18n import get_i18n

router_with_repl_kb = Router()

@router_with_repl_kb.message(I18nKeyFilter("Product catalog"))
async def handle_catalog_message(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id, message.from_user.username)
    await send_message(chat_id=user.user_id, image_key='main_catalog', reply_markup=catalog_kb(user.language))
