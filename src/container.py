from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_config
from src.infrastructure.files.file_system import FileStorage
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.redis import get_redis
from src.infrastructure.telegram.rate_limit import RateLimiter
from src.repository.database.replanishments import ReplenishmentsRepository
from src.services.models.module import ProfileModule
from src.repository.database.admins import (
    AdminActionsRepository,
    AdminsRepository,
    MessageForSendingRepository, SentMasMessagesRepository,
)
from src.repository.database.base import DatabaseBase
from src.repository.database.systems import (
    StickersRepository,
    UiImagesRepository, FilesRepository, SettingsRepository,
)
from src.repository.database.users import (
    BannedAccountsRepository,
    NotificationSettingsRepository,
    UserAuditLogsRepository,
    UsersRepository, TransferMoneysRepository, WalletTransactionRepository,
)
from src.repository.redis import (
    AdminsCacheRepository,
    BannedAccountsCacheRepository,
    StickersCacheRepository,
    SubscriptionCacheRepository,
    UiImagesCacheRepository,
    UsersCacheRepository, SettingsCacheRepository,
)
from src.services.bot import Messages, MassTgMailingService, SendFileService, SendLogs
from src.services.bot.edit_message import EditMessageService
from src.services.bot.send_message import SendMessageService
from src.services.bot.sticker_sender import StickerSender
from src.services.events.publish_event_handler import PublishEventHandler
from src.services.models.admins import AdminActionsService, AdminsService, MessageForSendingService, \
    SentMassMessagesService
from src.services.models.systems import StickersService, UiImagesService, FilesService, SettingsService
from src.services.models.users import (
    BannedAccountService,
    UserLogService,
    UserService,
    WalletTransactionService, MoneyTransferService, ReplenishmentsService,
)
from src.services.models.users.notifications_service import NotificationSettingsService
from src.services.models.users.permission_service import PermissionService
from src.utils.core_logger import get_logger


if TYPE_CHECKING:
    from src.infrastructure.telegram.client import TelegramClient


class Container:
    """
    Контейнер для сборки сервисного слоя. Вызывается строго только в middleware!
    """

    def __init__(
        self,
        session_db: AsyncSession,
        telegram_client : "TelegramClient",
        telegram_logger_client: "TelegramClient",
    ):
        self.session_db = session_db
        self.telegram_client = telegram_client
        self.telegram_logger_client = telegram_logger_client

        self.config = get_config()
        self.logger = get_logger(__name__)
        self.session_redis = get_redis()
        self.database_base = DatabaseBase(
            session_db=session_db,
            config=self.config,
        )
        self.publish_event_handler = PublishEventHandler()
        self.path_builder = PathBuilder(self.config)
        self.file_storage = FileStorage()

        self.wallet_transaction_repo = WalletTransactionRepository(
            session_db=session_db,
            config=self.config,
        )
        self.wallet_transaction_service = WalletTransactionService(
            wallet_transaction=self.wallet_transaction_repo,
            session_db=session_db,
        )
        self.settings_service = SettingsService(
            settings_repo=SettingsRepository(
                session_db=session_db,
                config=self.config,
            ),
            cache_repo=SettingsCacheRepository(
                redis_session=self.session_redis,
                config=self.config,
            ),
            conf=self.config,
            session_db=session_db
        )

        self.users_repo = UsersRepository(
            session_db=session_db,
            config=self.config,
        )
        self.user_log_repo = UserAuditLogsRepository(
            session_db=session_db,
            config=self.config,
        )
        self.notification_repo = NotificationSettingsRepository(
            session_db=session_db,
            config=self.config,
        )
        self.banned_accounts_repo = BannedAccountsRepository(
            session_db=session_db,
            config=self.config,
        )
        self.ui_image_repo = UiImagesRepository(
            session_db=session_db,
            config=self.config,
        )

        self.stickers_repo = StickersRepository(
            session_db=session_db,
            config=self.config,
        )

        self.users_cache_repo = UsersCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.subscription_cache_repo = SubscriptionCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.banned_accounts_cache_repo = BannedAccountsCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.ui_images_cache_repo = UiImagesCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.stickers_cache_repo = StickersCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )

        self.admin_actions_repo = AdminActionsRepository(
            session_db=session_db,
            config=self.config,
        )
        self.message_for_sending_repo = MessageForSendingRepository(
            session_db=session_db,
            config=self.config,
        )

        self.ui_images_service = UiImagesService(
            ui_image_repo=self.ui_image_repo,
            cache_repo=self.ui_images_cache_repo,
            session_db=session_db,
        )
        self.sent_mass_message_service = SentMassMessagesService(
            sent_msg_repo=SentMasMessagesRepository(
                session_db=session_db,
                config=self.config,
            ),
            session_db=session_db
        )
        self.files_service = FilesService(
            files_repo=FilesRepository(
                session_db=session_db,
                config=self.config,
            ),
            session_db=session_db
        )

        self.stickers_service = StickersService(
            sticker_repo=self.stickers_repo,
            cache_repo=self.stickers_cache_repo,
            conf=self.config,
            session_db=session_db,
        )

        self.user_log_service = UserLogService(
            log_repo=self.user_log_repo,
            session_db=session_db,
        )

        self.notification_service = NotificationSettingsService(
            notif_repo=self.notification_repo,
            session_db=session_db,
        )

        self.user_service = UserService(
            user_repo=self.users_repo,
            cache_user_repo=self.users_cache_repo,
            cache_subscription_repo=self.subscription_cache_repo,
            notif_service=self.notification_service,
            log_service=self.user_log_service,
            conf=self.config,
            session_db=session_db,
        )

        self.banned_account_service = BannedAccountService(
            banned_repo=self.banned_accounts_repo,
            cache_repo=self.banned_accounts_cache_repo,
            session_db=session_db,
        )

        self.admin_actions_service = AdminActionsService(
            admin_actions_repo=self.admin_actions_repo,
            session_db=session_db,
        )

        self.msg_for_sending_service = MessageForSendingService(
            msg_for_sending_repo=self.message_for_sending_repo,
            session_db=session_db,
        )

        self.admin_repo = AdminsRepository(
            session_db=session_db,
            config=self.config,
        )
        self.admin_cache_repo = AdminsCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.admin_service = AdminsService(
            admin_repo=self.admin_repo,
            cache_repo=self.admin_cache_repo,
            wallet_transaction_repo=self.wallet_transaction_service,
            admin_actions_service=self.admin_actions_service,
            user_service=self.user_service,
            ui_images_service=self.ui_images_service,
            msg_for_sending_service=self.msg_for_sending_service,
            banned_acc_service=self.banned_account_service,
            log_service=self.user_log_service,
            publish_event=self.publish_event_handler,
            session_db=session_db,
        )
        self.permission_service = PermissionService(admin_service=self.admin_service)

        self.transfer_moneys_repo = TransferMoneysRepository(
            session_db=session_db,
            config=self.config,
        )
        self.money_transfer_service = MoneyTransferService(
            transfer_repo=self.transfer_moneys_repo,
            user_log_service=self.user_log_service,
            user_service=self.user_service,
            user_cache_repo=self.users_cache_repo,
            wallet_trans_service=self.wallet_transaction_service,
            session_db=session_db,
            conf=self.config,
            logger=self.logger,
        )
        self.replenishment_repo = ReplenishmentsRepository(
            session_db=session_db,
            config=self.config,
        )
        self.replenishment_service = ReplenishmentsService(
            replenishment_repo=self.replenishment_repo,
            user_service=self.user_service,
            user_log_service=self.user_log_service,
            wallet_transaction_service=self.wallet_transaction_service,
            session_db=self.session_db,
        )

    def get_message_service(self,) -> Messages:
        rate_limiter = RateLimiter(
            max_calls=self.config.different.rate_send_msg_limit,
            period=1.0,
        )
        sticker_sender = StickerSender(
            tg_client=self.telegram_client,
            sticker_service=self.stickers_service,
        )

        send_msg_logger = get_logger("send_message_service")
        edit_msg_logger = get_logger("edit_message_service")
        send_msg_service = SendMessageService(
            tg_client=self.telegram_client,
            path_builder=self.path_builder,
            ui_images_service=self.ui_images_service,
            limiter=rate_limiter,
            sticker_sender=sticker_sender,
            file_system=self.file_storage,
            publish_event=self.publish_event_handler,
            logger=send_msg_logger,
        )
        edit_msg_service = EditMessageService(
            tg_client=self.telegram_client,
            send_msg_service=send_msg_service,
            path_builder=self.path_builder,
            ui_images_service=self.ui_images_service,
            limiter=rate_limiter,
            sticker_sender=sticker_sender,
            file_system=self.file_storage,
            publish_event=self.publish_event_handler,
            logger=edit_msg_logger,
        )
        mass_tg_mailing_service = MassTgMailingService(
            tg_client=self.telegram_client,
            limiter=rate_limiter,
            users_repo=self.users_repo,
            sent_mass_msg_service=self.sent_mass_message_service,
            conf=self.config,
            logger=edit_msg_logger,
        )
        send_file_service = SendFileService(
            tg_client=self.telegram_client,
            path_builder=self.path_builder,
            limiter=rate_limiter,
            sticker_sender=sticker_sender,
            file_system=self.file_storage,
            publish_event=self.publish_event_handler,
            logger=edit_msg_logger,
            files_service=self.files_service,
        )
        send_log_service = SendLogs(
            tg_logger_client=self.telegram_logger_client,
            limiter=rate_limiter,
            settings_service=self.settings_service,
            conf=self.config,
            logger=edit_msg_logger,
        )
        return Messages(
            send_msg=send_msg_service,
            edit_msg=edit_msg_service,
            mass_tg_mailing=mass_tg_mailing_service,
            send_file=send_file_service,
            send_log=send_log_service,
            sticker_sender=sticker_sender,
        )

    def get_profile_modul(self,) -> ProfileModule:
        return ProfileModule(
            conf=self.config,
            user_service=self.user_service,
            permission_service=self.permission_service,
            wallet_transaction_service=self.wallet_transaction_service,
            money_transfer_service=self.money_transfer_service,
        )


def init_container(
    session_db: AsyncSession,
    telegram_client: "TelegramClient",
    telegram_logger_client: "TelegramClient",
) -> Container:
    return Container(session_db, telegram_client, telegram_logger_client)
