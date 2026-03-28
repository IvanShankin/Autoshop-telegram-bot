import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_config
from src.exceptions import UserNotFound, AdminNotFound, UnableRemoveMainAdmin
from src.models.create_models.admins import CreateAdminAction
from src.models.create_models.users import CreateBannedAccountsDTO, CreateUserAuditLogDTO, CreateWalletTransactionDTO
from src.models.read_models import AdminsDTO
from src.models.update_models import UpdateUserDTO
from src.repository.database.admins import AdminsRepository, AdminActionsRepository
from src.repository.redis import AdminsCacheRepository
from src.services.filesystem.actions import get_default_image_bytes
from src.services.models.admins.admin_action_service import AdminActionsService
from src.services.models.admins.message_for_sending_service import MessageForSendingService
from src.services.models.systems.ui_image_service import UiImagesService
from src.services.models.users.banned_account_service import BannedAccountService
from src.services.models.users.user_log_service import UserLogService
from src.services.models.users.user_service import UserService
from src.services.models.users.wallet_transaction import WalletTransactionService
from src.services.publish_event_handler import PublishEventHandler


class AdminsService:

    def __init__(
        self,
        admin_repo: AdminsRepository,
        cache_repo: AdminsCacheRepository,
        wallet_transaction_repo: WalletTransactionService,
        admin_actions_service: AdminActionsService,
        user_service: UserService,
        ui_images_service: UiImagesService,
        msg_for_sending_service: MessageForSendingService,
        banned_acc_service: BannedAccountService,
        log_service: UserLogService,
        session_db: AsyncSession,
    ):
        self.admin_repo = admin_repo
        self.cache_repo = cache_repo
        self.wallet_transaction_repo = wallet_transaction_repo
        self.admin_actions_service = admin_actions_service
        self.user_service = user_service
        self.ui_images_service = ui_images_service
        self.msg_for_sending_service = msg_for_sending_service
        self.banned_acc_service = banned_acc_service
        self.log_service = log_service
        self.session_db = session_db

    async def check_admin(self, user_id: int) -> bool:
        return await self.cache_repo.exists(user_id)

    async def create_admin(self, user_id: int) -> AdminsDTO:
        user = await self.user_service.get_user(user_id=user_id)

        if not user:
            raise UserNotFound()

        admin = await self.admin_repo.get_admin_by_user_id(user_id=user_id)
        if admin:
            return admin

        async with self.session_db.begin():
            admin = await self.admin_repo.create_admin(user_id=user_id)
            ui_image = await self.ui_images_service.create_default_io_image()

            if not await self.msg_for_sending_service.get_msg(user_id):
                await self.msg_for_sending_service.create_msg(user_id=user_id, ui_image_key=ui_image.key)

            await self.session_db.commit()
            await self.cache_repo.set(user_id)
        await self.ui_images_service.cache_repo.set(ui_image)
        return admin



    async def delete_admin(self, user_id: int) -> None:
        """
        :except UnableRemoveMainAdmin
        :except AdminNotFound
        """
        if user_id == get_config().env.main_admin:
            raise UnableRemoveMainAdmin()

        if not await self.check_admin(user_id):
            raise AdminNotFound()

        msg_for_sent = await self.msg_for_sending_service.get_msg(user_id=user_id)

        async with self.session_db.begin():
            await self.admin_repo.delete_admin(user_id=user_id)
            if msg_for_sent:
                await self.msg_for_sending_service.delete_msg(user_id=user_id)
                await self.ui_images_service.delete_ui_image(key=msg_for_sent.ui_image_key)

            await self.session_db.commit()

        await self.cache_repo.delete(user_id=user_id)

    async def create_banned_account(self, admin_id: int, user_id: int, reason: str) -> None:
        """
        Создаст новый забаненный аккаунт, залогирует и отошлёт в канал данное действие админа
        :param admin_id: id админа который это сделал
        :param user_id: id пользователя
        :param reason: Причина
        :exception UserNotFound: Если пользователь не найден
        """
        if not await self.user_service.get_user(user_id):
            raise UserNotFound(f"Пользователь с id = {user_id} не найден")

        await self.banned_acc_service.create_ban(
            user_id=user_id,
            data=CreateBannedAccountsDTO(reason=reason),
            make_commit=True,
            filling_redis=True
        )

        await self.admin_actions_service.create_admin_action(
            user_id=admin_id,
            data=CreateAdminAction(
                action_type="added ban account",
                message="Добавил аккаунт в забаненные",
                details={"user_id": user_id}
            ),
            make_commit=True
        )

        await PublishEventHandler.ban_account(admin_id=admin_id, user_id=user_id, reason=reason)

    async def delete_banned_account(self, admin_id: int, user_id: int) -> None:
        """
        :exception UserNotFound: Если пользователь не забанен
        """
        if not await self.banned_acc_service.get_ban(user_id=user_id):
            raise UserNotFound(f"Пользователь с id = {user_id} не забанен")

        await self.banned_acc_service.delete_ban(
            user_id=user_id,
            make_commit=True,
            filling_redis=True
        )

        await self.admin_actions_service.create_admin_action(
            user_id=admin_id,
            data=CreateAdminAction(
                action_type="deleted ban account",
                message="Удалил аккаунт из забаненных",
                details={"user_id": user_id}
            ),
            make_commit=True
        )

        await PublishEventHandler.delete_ban_account(admin_id=admin_id, user_id=user_id)

    async def admin_update_user_balance(self, admin_id: int, target_user_id: int, new_balance: int) -> None:
        """
        :exception UserNotFound: Если по target_user_id не найден пользователь
        """
        target_user = await self.user_service.get_user(target_user_id)
        if not target_user:
            raise UserNotFound()

        async with self.session_db.begin():
            user = await self.user_service.update_user(
                user_id=target_user_id,
                data=UpdateUserDTO(balance=new_balance)
            )

            action = await self.admin_actions_service.create_admin_action(
                user_id=admin_id,
                data=CreateAdminAction(
                    action_type="update_user_balance",
                    message="Изменил баланс пользователя",
                    details={
                        "target_user_id": target_user_id,
                        "balance_before": target_user.balance,
                        "balance_after": new_balance,
                    }
                )
            )

            new_transaction = await self.wallet_transaction_repo.create_wallet_transaction(
                user_id=target_user_id,
                data=CreateWalletTransactionDTO(
                    type="admin_actions",
                    amount=new_balance - target_user.balance,
                    balance_before=target_user.balance,
                    balance_after=new_balance,
                ),
            )

            await self.log_service.create_log(
                user_id=target_user_id,
                data=CreateUserAuditLogDTO(
                    action_type="admin_update_balance",
                    message="Админ изменил баланс пользователю",
                    details={
                        "wallet_transaction_id": new_transaction.wallet_transaction_id,
                        "admin_action_id": action.admin_action_id,
                    }
                )
            )
            await self.session_db.commit()

        await self.user_service.cache_user_repo.set(
            user=user, ttl=self.user_service.conf.redis_time_storage.user.total_seconds()
        )

        await PublishEventHandler.admin_update_balance(
            admin_id=admin_id,
            target_user_id=target_user_id,
            balance_before=target_user.balance,
            balance_after=new_balance
        )
