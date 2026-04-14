from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.keyboard_main import info_kb
from src.database.models.users import Users

router_with_repl_kb = Router()


@router_with_repl_kb.message(I18nKeyFilter("information"))
async def handle_catalog_message(
    message: Message, state: FSMContext, user: Users, admin_module: AdminModule, messages_service: Messages
):
    await state.clear()

    await messages_service.send_msg.send(
        user.user_id,
        reply_markup=await info_kb(user.language, admin_module),
        event_message_key="info",
    )