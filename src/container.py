from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot_actions.bot_instance import get_bot, get_bot_logger
from src.config import get_config
from src.infrastructure.files.file_system import FileStorage
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.redis import get_redis
from src.infrastructure.telegram.client import TelegramClient
from src.infrastructure.telegram.rate_limit import RateLimiter
from src.modules.profile.module import ProfileModule
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
    WalletTransactionService, MoneyTransferService,
)
from src.services.models.users.notifications_service import NotificationSettingsService
from src.services.models.users.permission_service import PermissionService
from src.utils.core_logger import get_logger


class Container:
    """
    Контейнер для сборки сервисного слоя. Вызывается строго только в middleware!
    """

    def __init__(self, session_db: AsyncSession):
        self._config = get_config()
        self._logger = get_logger(__name__)
        self._session_redis = get_redis()
        self._database_base = DatabaseBase(
            session_db=session_db,
            config=self._config,
        )
        self._publish_event_handler = PublishEventHandler()
        self._bot = get_bot()
        self._logger_bot = get_bot_logger()
        self._telegram_client = TelegramClient(bot=self._bot)
        self._telegram_logger_client = TelegramClient(bot=self._logger_bot)
        self._path_builder = PathBuilder(self._config)
        self._file_storage = FileStorage()

        self._wallet_transaction_repo = WalletTransactionRepository(
            session_db=session_db,
            config=self._config,
        )
        self._wallet_transaction_service = WalletTransactionService(
            wallet_transaction=self._wallet_transaction_repo,
            session_db=session_db,
        )
        self._settings_service = SettingsService(
            settings_repo=SettingsRepository(
                session_db=session_db,
                config=self._config,
            ),
            cache_repo=SettingsCacheRepository(
                redis_session=self._session_redis,
                config=self._config,
            ),
            conf=self._config,
            session_db=session_db
        )

        self._users_repo = UsersRepository(
            session_db=session_db,
            config=self._config,
        )
        self._user_log_repo = UserAuditLogsRepository(
            session_db=session_db,
            config=self._config,
        )
        self._notification_repo = NotificationSettingsRepository(
            session_db=session_db,
            config=self._config,
        )
        self._banned_accounts_repo = BannedAccountsRepository(
            session_db=session_db,
            config=self._config,
        )
        self._ui_image_repo = UiImagesRepository(
            session_db=session_db,
            config=self._config,
        )

        self._stickers_repo = StickersRepository(
            session_db=session_db,
            config=self._config,
        )

        self._users_cache_repo = UsersCacheRepository(
            redis_session=self._session_redis,
            config=self._config,
        )
        self._subscription_cache_repo = SubscriptionCacheRepository(
            redis_session=self._session_redis,
            config=self._config,
        )
        self._banned_accounts_cache_repo = BannedAccountsCacheRepository(
            redis_session=self._session_redis,
            config=self._config,
        )
        self._ui_images_cache_repo = UiImagesCacheRepository(
            redis_session=self._session_redis,
            config=self._config,
        )
        self._stickers_cache_repo = StickersCacheRepository(
            redis_session=self._session_redis,
            config=self._config,
        )

        self._admin_actions_repo = AdminActionsRepository(
            session_db=session_db,
            config=self._config,
        )
        self._message_for_sending_repo = MessageForSendingRepository(
            session_db=session_db,
            config=self._config,
        )

        self._ui_images_service = UiImagesService(
            ui_image_repo=self._ui_image_repo,
            cache_repo=self._ui_images_cache_repo,
            session_db=session_db,
        )
        self._sent_mass_message_service = SentMassMessagesService(
            sent_msg_repo=SentMasMessagesRepository(
                session_db=session_db,
                config=self._config,
            ),
            session_db=session_db
        )
        self._files_service = FilesService(
            files_repo=FilesRepository(
                session_db=session_db,
                config=self._config,
            ),
            session_db=session_db
        )

        self._stickers_service = StickersService(
            sticker_repo=self._stickers_repo,
            cache_repo=self._stickers_cache_repo,
            conf=self._config,
            session_db=session_db,
        )

        self._user_log_service = UserLogService(
            log_repo=self._user_log_repo,
            session_db=session_db,
        )

        self._notification_service = NotificationSettingsService(
            notif_repo=self._notification_repo,
            session_db=session_db,
        )

        self._user_service = UserService(
            user_repo=self._users_repo,
            cache_user_repo=self._users_cache_repo,
            cache_subscription_repo=self._subscription_cache_repo,
            notif_service=self._notification_service,
            log_service=self._user_log_service,
            conf=self._config,
            session_db=session_db,
        )

        self._banned_account_service = BannedAccountService(
            banned_repo=self._banned_accounts_repo,
            cache_repo=self._banned_accounts_cache_repo,
            session_db=session_db,
        )

        self._admin_actions_service = AdminActionsService(
            admin_actions_repo=self._admin_actions_repo,
            session_db=session_db,
        )

        self._msg_for_sending_service = MessageForSendingService(
            msg_for_sending_repo=self._message_for_sending_repo,
            session_db=session_db,
        )

        self._admin_repo = AdminsRepository(
            session_db=session_db,
            config=self._config,
        )
        self._admin_cache_repo = AdminsCacheRepository(
            redis_session=self._session_redis,
            config=self._config,
        )
        self._admin_service = AdminsService(
            admin_repo=self._admin_repo,
            cache_repo=self._admin_cache_repo,
            wallet_transaction_repo=self._wallet_transaction_service,
            admin_actions_service=self._admin_actions_service,
            user_service=self._user_service,
            ui_images_service=self._ui_images_service,
            msg_for_sending_service=self._msg_for_sending_service,
            banned_acc_service=self._banned_account_service,
            log_service=self._user_log_service,
            publish_event=self._publish_event_handler,
            session_db=session_db,
        )
        self._permission_service = PermissionService(admin_service=self._admin_service)

        self.transfer_moneys_repo = TransferMoneysRepository(
            session_db=session_db,
            config=self._config,
        )
        self._money_transfer_service = MoneyTransferService(
            transfer_repo=self.transfer_moneys_repo,
            user_log_service=self._user_log_service,
            user_service=self._user_service,
            user_cache_repo=self._users_cache_repo,
            wallet_trans_service=self._wallet_transaction_service,
            session_db=session_db,
            conf=self._config,
            logger=self._logger,
        )

    def get_message_service(self,) -> Messages:
        _rate_limiter = RateLimiter(
            max_calls=self._config.different.rate_send_msg_limit,
            period=1.0,
        )
        _sticker_sender = StickerSender(
            tg_client=self._telegram_client,
            sticker_service=self._stickers_service,
        )

        _send_msg_logger = get_logger("send_message_service")
        _edit_msg_logger = get_logger("edit_message_service")
        _send_msg_service = SendMessageService(
            tg_client=self._telegram_client,
            path_builder=self._path_builder,
            ui_images_service=self._ui_images_service,
            limiter=_rate_limiter,
            sticker_sender=_sticker_sender,
            file_system=self._file_storage,
            publish_event=self._publish_event_handler,
            logger=_send_msg_logger,
        )
        _edit_msg_service = EditMessageService(
            tg_client=self._telegram_client,
            send_msg_service=_send_msg_service,
            path_builder=self._path_builder,
            ui_images_service=self._ui_images_service,
            limiter=_rate_limiter,
            sticker_sender=_sticker_sender,
            file_system=self._file_storage,
            publish_event=self._publish_event_handler,
            logger=_edit_msg_logger,
        )
        _mass_tg_mailing_service = MassTgMailingService(
            tg_client=self._telegram_client,
            limiter=_rate_limiter,
            users_repo=self._users_repo,
            sent_mass_msg_service=self._sent_mass_message_service,
            conf=self._config,
            logger=_edit_msg_logger,
        )
        _send_file = SendFileService(
            tg_client=self._telegram_client,
            path_builder=self._path_builder,
            limiter=_rate_limiter,
            sticker_sender=_sticker_sender,
            file_system=self._file_storage,
            publish_event=self._publish_event_handler,
            logger=_edit_msg_logger,
            files_service=self._files_service,
        )
        _send_log = SendLogs(
            tg_logger_client=self._telegram_logger_client,
            limiter=_rate_limiter,
            settings_service=self._settings_service,
            conf=self._config,
            logger=_edit_msg_logger,
        )
        _sticker_sender = StickerSender(
            tg_client=self._telegram_client,
            sticker_service=self._stickers_service
        )
        return Messages(
            send_msg=_send_msg_service,
            edit_msg=_edit_msg_service,
            mass_tg_mailing=_mass_tg_mailing_service,
            send_file=_send_file,
            send_log=_send_log,
            sticker_sender=_sticker_sender
        )

    def get_profile_modul(self,) -> ProfileModule:
        return ProfileModule(
            conf=self._config,
            user_service=self._user_service,
            permission_service=self._permission_service,
            wallet_transaction_service=self._wallet_transaction_service,
            money_transfer_service=self._money_transfer_service,
        )


def init_container(session_db: AsyncSession) -> Container:
    return Container(session_db)
