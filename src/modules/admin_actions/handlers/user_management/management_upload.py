from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile

from src.bot_actions.bot_instance import get_bot
from src.services.products.accounts.utils.generate_report import get_user_audit_log_bites
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data.startswith("unload_action_user:"))
async def unload_action_user(callback: CallbackQuery, state: FSMContext, user: Users):
    target_user_id = int(callback.data.split(':')[1])
    try:
        stream_excel = await get_user_audit_log_bites(target_user_id)
    except ValueError: # по сути даже не должны сюда попасть, т.к. при регистрации пользователя создаётся лог
        await callback.answer(
            get_text(user.language, "admins_user_mang", "user_has_no_log_entries"),
            show_alert=True
        )
        return

    bot = await get_bot()
    await bot.send_document(
        user.user_id,
        document=BufferedInputFile(
            stream_excel,
            filename="User audit log.csv"
        )
    )
