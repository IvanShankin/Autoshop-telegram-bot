from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, BufferedInputFile

from src.bot_actions.actions import edit_message, send_message
from src.bot_actions.bot_instance import get_bot
from src.modules.admin_actions.handlers.user_management.keyboard import user_management_kb, back_in_user_management_kb
from src.modules.admin_actions.keyboard_main import back_in_main_admin_kb
from src.modules.admin_actions.schemas.user_management import SetNewBalanceData
from src.modules.admin_actions.state.user_management import GetUserIdOrUsername, SetNewBalance
from src.modules.profile.services.profile_message import get_main_message_profile
from src.services.accounts.utils.generate_report import get_user_audit_log_bites
from src.services.database.admins.actions.actions_admin import add_admin_action
from src.services.database.users.actions import get_user
from src.services.database.users.actions.action_user import get_user_by_username, update_user, admin_update_user_balance
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data.startswith("unload_action_user:"))
async def unload_action_user(callback: CallbackQuery, state: FSMContext, user: Users):
    target_user_id = int(callback.data.split(':')[1])
    stream_csv = await get_user_audit_log_bites(target_user_id)
    bot = await get_bot()
    await bot.send_document(
        user.user_id,
        document=BufferedInputFile(
            stream_csv,
            filename=get_text(user.language, "admins_editor", "User audit log") + '.csv' # добавить перевод
        )
    )

    # добавть обработку исключение если записей нет
    # добавть обработку исключение если записей нет
    # добавть обработку исключение если записей нет

    # добавить перевод
    # добавить перевод
    # добавить перевод
    # добавить перевод