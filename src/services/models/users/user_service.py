from datetime import datetime, UTC
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.config import Config
from src.database.models.users import Users
from src.infrastructure.rebbit_mq.producer import publish_event
from src.models.create_models.users import CreateUserDTO, CreateUserAuditLogDTO
from src.models.read_models import UsersDTO
from src.models.update_models.users import UpdateUserDTO
from src.repository.database.users import UsersRepository
from src.repository.redis import UsersCacheRepository, SubscriptionCacheRepository
from src.services.models.users.notifications_service import NotificationSettingsService
from src.services.models.users.user_log_service import UserLogService
from src.utils.codes import generate_code


class UserService:

    def __init__(
        self,
        user_repo: UsersRepository,
        cache_user_repo: UsersCacheRepository,
        cache_subscription_repo: SubscriptionCacheRepository,
        notif_service: NotificationSettingsService,
        log_service: UserLogService,
        conf: Config,
        session_db: AsyncSession
    ):
        self.conf = conf
        self.user_repo = user_repo
        self.cache_user_repo = cache_user_repo
        self.cache_subscription_repo = cache_subscription_repo
        self.notif_service = notif_service
        self.log_service = log_service
        self.session_db = session_db

    async def _create_unique_referral_code(self) -> str:
        while True:
            code = generate_code()
            user = await self.user_repo.get_by_referral_code(code)

            if user:  # если данный код уже занят пользователем
                continue
            else:
                return str(code)

    async def get_user(
        self,
        user_id: int,
        username: Optional[str] = False,
        update_last_used: Optional[bool] = False
    ) -> Optional[UsersDTO]:
        """
        :param username: Обновит username если он не сходится с имеющимся
        """
        user = await self.cache_user_repo.get(user_id)
        if user:
            if username is not False and user.username != username: # если username расходится
                await self.user_repo.update(user_id=user_id, username=username)
            return user

        user_db = await self.user_repo.get_by_id(user_id)
        if user_db:
            update_data = {}

            if username is not False and user_db.username != username:
                update_data["username"] = username
                user_db.username = username
            if update_last_used:
                last_used = datetime.now(UTC)
                update_data["last_used"] = last_used
                user_db.last_used = last_used

            if update_data:
                await self.user_repo.update(user_id=user_id, **update_data)

            await self.cache_user_repo.set(user=user_db, ttl=self.conf.redis_time_storage.user.total_seconds())

            return user_db

        return None

    async def get_user_for_update(self, user_id: int) -> Optional[Users]:
        return await self.user_repo.get_by_id_for_update(user_id)

    async def get_user_by_ref_code(self, code: str) -> Optional[UsersDTO]:
        return await self.user_repo.get_by_referral_code(code)

    async def get_user_by_username(self, username: str) -> Sequence[UsersDTO]:
        """Вернётся список пользователей т.к. в БД может быть такая ситуация когда имеется 2 и более одинаковых username"""
        return await self.user_repo.get_by_username(username)

    async def get_quantity_users(self):
        return await self.user_repo.count_all()

    async def create_user(self, data: CreateUserDTO) -> UsersDTO:
        values = data.model_dump(exclude_unset=True)
        unique_referral_code = self._create_unique_referral_code()

        async with self.session_db.begin():
            user = await self.user_repo.create_user(unique_referral_code=unique_referral_code, **values)
            await self.notif_service.create_notification(user.user_id)
            await self.log_service.create_log(
                user_id=user.user_id,
                data=CreateUserAuditLogDTO(
                    action_type="new_user",
                    message="Пользователь зарегистрировался в боте"
                ),
                make_commit=False
            )
            await self.session_db.commit()

        await self.cache_user_repo.set(user=user, ttl=self.conf.redis_time_storage.user.total_seconds())
        await self.cache_subscription_repo.set(
            user_id=user.user_id, ttl=self.conf.redis_time_storage.subscription_prompt.total_seconds()
        )

        event = EventSentLog(
            text=f"#Новый_пользователь \n\nID: {user.user_id}\nusername: {user.username}",
            log_lvl=LogLevel.INFO
        )
        await publish_event(event.model_dump(), "message.send_log")

        return user

    async def update_user(
        self,
        user_id: int,
        data: UpdateUserDTO,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> Optional[UsersDTO]:
        values = data.model_dump(exclude_unset=True)
        user = await self.user_repo.update(user_id, **values)

        if make_commit:
            await self.session_db.commit()

        if user and filling_redis:
            await self.cache_user_repo.set(user=user, ttl=self.conf.redis_time_storage.user.total_seconds())

        return user



