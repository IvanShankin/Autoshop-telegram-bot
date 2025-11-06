from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot_actions.actions import send_message, edit_message
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.catalog.keyboard_catalog import catalog_kb
from src.services.database.users.actions import get_user

router_with_repl_kb = Router()
router = Router()

@router_with_repl_kb.message(I18nKeyFilter("Product catalog"))
async def handle_catalog_message(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id, message.from_user.username)
    await send_message(
        chat_id=user.user_id,
        image_key='main_catalog',
        fallback_image_key="default_catalog_account",
        reply_markup=catalog_kb(user.language)
    )

@router.callback_query(F.data == "catalog")
async def handle_catalog_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(callback.from_user.id, callback.from_user.username)
    await edit_message(
        message_id=callback.message.message_id,
        chat_id=user.user_id,
        image_key='main_catalog',
        reply_markup=catalog_kb(user.language)
    )