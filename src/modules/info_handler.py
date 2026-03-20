from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot_actions.messages import send_message
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.keyboard_main import info_kb
from src.database.models.users import Users

router_with_repl_kb = Router()


@router_with_repl_kb.message(I18nKeyFilter("information"))
async def handle_catalog_message(message: Message, state: FSMContext, user: Users):
    await state.clear()

    await send_message(
        user.user_id,
        reply_markup=await info_kb(user.language),
        event_message_key="info",
    )