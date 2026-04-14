from src.application.models.users import UserLogService
from src.config import Config
from src.infrastructure.files.file_system import make_csv_bytes


class GenerateUserAuditLogUseCase:

    def __init__(
        self,
        conf: Config,
        user_log_service: UserLogService,
    ):
        self.conf = conf
        self.user_log_service = user_log_service


    async def get_user_audit_log_bites(self, user_id: int) -> bytes:
        """
        :return: поток байтов для формирования excel файла
        :except ValueError: Если нет логов
        """
        logs = await self.user_log_service.get_all_by_user(user_id)
        ready_logs = []
        for log in logs:
            need_dict = log.model_dump()
            need_dict["created_at"] = log.created_at.strftime(self.conf.different.dt_format)
            ready_logs.append(need_dict)

        return make_csv_bytes(ready_logs, ["user_audit_log_id", "user_id", "action_type", "message", "details", "created_at"])