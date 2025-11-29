from src.bot_actions.messages import send_message, edit_message
from src.modules.admin_actions.handlers.user_management.keyboard import user_management_kb
from src.modules.profile.services.profile_message import get_main_message_profile
from src.services.database.users.actions import get_banned_account
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def message_about_user(new_message: bool, admin: Users, target_user: Users, message_id: int = None):
    result_message = await get_main_message_profile(target_user, admin.language)
    reason_ban = await get_banned_account(target_user.user_id)
    if reason_ban:
        result_message += get_text(
            admin.language,
            "admins_user_mang",
            "\n\nReason for ban: {reason}"
        ).format(reason=reason_ban)

    if new_message:
        await send_message(
            admin.user_id,
            result_message,
            image_key="admin_panel",
            reply_markup=user_management_kb(admin.language, target_user.user_id, bool(reason_ban))
        )
    else:
        await edit_message(
            admin.user_id,
            message_id=message_id,
            message=result_message,
            image_key="admin_panel",
            reply_markup=user_management_kb(admin.language, target_user.user_id, bool(reason_ban))
        )