from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.services.editor.category.show_message import edit_message_in_main_category_editor, show_category

router = Router()


@router.callback_query(F.data.startswith("show_category_admin:"))
async def show_category_admin(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    await state.clear()
    category_id = int(callback.data.split(':')[1])
    await show_category(
        user=user,
        category_id=category_id,
        admin_module=admin_module,
        messages_service=messages_service,
        message_id=callback.message.message_id,
        callback=callback,
    )


@router.callback_query(F.data == "category_editor")
async def category_editor(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
):
    await state.clear()
    await edit_message_in_main_category_editor(
        user=user,
        callback=callback,
        admin_module=admin_module,
        messages_service=messages_service,
    )