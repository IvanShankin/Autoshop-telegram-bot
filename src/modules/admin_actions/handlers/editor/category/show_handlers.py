from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.modules.admin_actions.services.editor.category.show_message import edit_message_in_main_category_editor, show_category
from src.services.database.users.models import Users

router = Router()


@router.callback_query(F.data.startswith("show_category_admin:"))
async def show_category_admin(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    category_id = int(callback.data.split(':')[1])
    await show_category(user=user, category_id=category_id, message_id=callback.message.message_id, callback=callback)


@router.callback_query(F.data == "category_editor")
async def category_editor(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message_in_main_category_editor(
        user=user,
        callback=callback
    )