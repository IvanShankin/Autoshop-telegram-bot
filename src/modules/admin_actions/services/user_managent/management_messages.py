from src.application.bot import Messages
from src.application.models.modules import ProfileModule, AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards.user_management_kb import user_management_kb
from src.modules.profile.services.profile_message import get_main_message_profile
from src.utils.i18n import get_text


async def message_about_user(
    new_message: bool, 
    admin: UsersDTO,
    target_user: UsersDTO, 
    profile_modul: ProfileModule,
    admin_module: AdminModule,
    messages_service: Messages,
    message_id: int = None
):
    result_message = await get_main_message_profile(target_user, admin.language, profile_modul)
    reason_ban = await admin_module.banned_account_service.get_ban(target_user.user_id)
    if reason_ban:
        result_message += get_text(
            admin.language,
            "admins_user_mang",
            "reason_for_ban"
        ).format(reason=reason_ban)

    if new_message:
        await messages_service.send_msg.send(
            admin.user_id,
            result_message,
            event_message_key="admin_panel",
            reply_markup=user_management_kb(admin.language, target_user.user_id, bool(reason_ban))
        )
    else:
        await messages_service.edit_msg.edit(
            admin.user_id,
            message_id=message_id,
            message=result_message,
            event_message_key="admin_panel",
            reply_markup=user_management_kb(admin.language, target_user.user_id, bool(reason_ban))
        )