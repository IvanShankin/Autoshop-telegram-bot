from src.config import get_config
from src.services.database.users.actions.action_other_with_user import get_all_user_audit_logs
from src.services.filesystem.account_products import make_csv_bytes


async def get_user_audit_log_bites(user_id: int) -> bytes:
    """
    :return: поток байтов для формирования excel файла
    :except ValueError: Если нет логов
    """
    logs = await get_all_user_audit_logs(user_id)
    ready_logs = []
    for log in logs:
        need_dict = log.to_dict()
        need_dict["created_at"] = log.created_at.strftime(get_config().different.dt_format)
        ready_logs.append(need_dict)

    return make_csv_bytes(ready_logs, ["user_audit_log_id", "user_id", "action_type", "message", "details", "created_at"])