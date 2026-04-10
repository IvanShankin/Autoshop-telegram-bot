from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_config
from src.infrastructure.crypto_bot.core import CryptoBotProvider
from src.infrastructure.files.excel_reports import ExcelReportExporter
from src.infrastructure.files.file_system import FileStorage
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.redis import get_redis
from src.infrastructure.telegram.rate_limit import RateLimiter
from src.repository.database.discount import VouchersRepository, VoucherActivationsRepository, PromoCodeRepository, \
    ActivatedPromoCodeRepository
from src.repository.database.refferals import ReferralsRepository, ReferralIncomeRepository, ReferralLevelsRepository
from src.repository.database.replanishments import ReplenishmentsRepository
from src.application.cache_warmup import CacheWarmupService
from src.application.events.event_handlers.file_system import FileSystemEventHandler
from src.application.events.event_handlers.main_event_handler import EventHandler
from src.application.events.event_handlers.message import MessageEventHandler
from src.application.events.event_handlers.promo_code import PromoCodeEventHandler
from src.application.events.event_handlers.purchase import PurchaseEventHandler
from src.application.events.event_handlers.referrals import ReferralEventHandler
from src.application.events.event_handlers.replenishments import ReplenishmentsEventHandler
from src.application.models.discounts import ActivatedPromoCodesService, PromoCodeService
from src.application.models.discounts.vouchers_service import VoucherService
from src.application.models.modules import ProfileModule, AccountsModuls, UniversalModuls
from src.repository.database.admins import (
    AdminActionsRepository,
    AdminsRepository,
    MessageForSendingRepository, SentMasMessagesRepository,
)
from src.repository.database.base import DatabaseBase
from src.repository.database.categories import (
    CategoriesRepository,
    DeletedAccountsRepository,
    ProductAccountsRepository,
    SoldAccountsRepository,
    SoldAccountsTranslationRepository,
    AccountStorageRepository,
    TgAccountMediaRepository,
    DeletedUniversalRepository,
    ProductUniversalRepository,
    SoldUniversalRepository,
    UniversalStorageRepository,
    UniversalTranslationRepository,
)
from src.repository.database.systems import (
    StickersRepository,
    UiImagesRepository, FilesRepository, SettingsRepository, TypePaymentsRepository,
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
    UsersCacheRepository, SettingsCacheRepository, VouchersCacheRepository, PromoCodesCacheRepository,
    ReferralLevelsCacheRepository, TypePaymentsCacheRepository, DollarRateRepository,
    AccountsCacheRepository,
    CategoriesCacheRepository,
    ProductUniversalCacheRepository,
    ProductUniversalSingleCacheRepository,
    SoldUniversalCacheRepository,
    SoldUniversalSingleCacheRepository,
)
from src.application.bot import Messages, MassTgMailingService, SendFileService, SendLogs
from src.application.bot.edit_message import EditMessageService
from src.application.bot.send_message import SendMessageService
from src.application.bot.sticker_sender import StickerSender
from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.admins import AdminActionsService, AdminsService, MessageForSendingService, \
    SentMassMessagesService
from src.application.models.payment_services import PaymentService
from src.application.models.referrals import ReferralService, ReferralIncomeService, ReferralLevelsService
from src.application.models.systems import StickersService, UiImagesService, FilesService, SettingsService, \
    TypesPaymentsService
from src.application.models.users import (
    BannedAccountService,
    UserLogService,
    UserService,
    WalletTransactionService, MoneyTransferService, ReplenishmentsService,
)
from src.application.models.users.notifications_service import NotificationSettingsService
from src.application.models.users.permission_service import PermissionService
from src.application.models.categories.categories_cache_filler_service import CategoriesCacheFillerService
from src.application.models.products.accounts import (
    AccountDeletedService,
    AccountProductService,
    AccountSoldService,
    AccountStorageService,
    AccountTgMediaService,
    AccountTranslationsService,
    AccountsCacheFillerService,
)
from src.application.models.products.universal import (
    UniversalCacheFillerService,
    UniversalDeletedService,
    UniversalProductService,
    UniversalSoldService,
    UniversalStorageService,
    UniversalTranslationsService,
)
from src.utils.core_logger import get_logger
from src.utils.i18n import get_text

if TYPE_CHECKING:
    from src.infrastructure.telegram.client import TelegramClient


class RequestContainer:
    """
    Контейнер для сборки сервисного слоя. Вызывается строго только в middleware!
    """

    def __init__(
        self,
        session_db: AsyncSession,
        telegram_client : "TelegramClient",
        telegram_logger_client: "TelegramClient",
        crypto_bot_provider: CryptoBotProvider,
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

        self.settings_repo = SettingsRepository(
            session_db=session_db,
            config=self.config,
        )
        self.settings_cache_repo = SettingsCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.settings_service = SettingsService(
            settings_repo=self.settings_repo,
            cache_repo=self.settings_cache_repo,
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

        self.deleted_universal_repo = DeletedUniversalRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.product_universal_repo = ProductUniversalRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.sold_universal_repo = SoldUniversalRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.universal_storage_repo = UniversalStorageRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.universal_translation_repo = UniversalTranslationRepository(
            session_db=self.session_db,
            config=self.config,
        )

        self.accounts_cache_repo = AccountsCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.product_accounts_repo = ProductAccountsRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.account_storage_repo = AccountStorageRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.sold_accounts_repo = SoldAccountsRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.sold_accounts_translation_repo = SoldAccountsTranslationRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.tg_account_media_repo = TgAccountMediaRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.deleted_accounts_repo = DeletedAccountsRepository(
            session_db=self.session_db,
            config=self.config,
        )

        self.user_service = UserService(
            user_repo=self.users_repo,
            cache_user_repo=self.users_cache_repo,
            cache_subscription_repo=self.subscription_cache_repo,
            notif_service=self.notification_service,
            log_service=self.user_log_service,
            conf=self.config,
            session_db=session_db,
            sold_universal_repo=self.sold_universal_repo,
            sold_accounts_repo=self.sold_accounts_repo,
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

        self.categories_repo = CategoriesRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.categories_cache_repo = CategoriesCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.categories_cache_filler_service = CategoriesCacheFillerService(
            category_repo=self.categories_repo,
            category_cache_repo=self.categories_cache_repo,
        )

        self.accounts_cache_filler_service = AccountsCacheFillerService(
            product_repo=self.product_accounts_repo,
            sold_repo=self.sold_accounts_repo,
            cache_repo=self.accounts_cache_repo,
        )

        self.account_storage_service = AccountStorageService(
            storage_repo=self.account_storage_repo,
            product_repo=self.product_accounts_repo,
            sold_repo=self.sold_accounts_repo,
            tg_media_repo=self.tg_account_media_repo,
            accounts_cache_filler=self.accounts_cache_filler_service,
            session_db=self.session_db,
        )
        self.account_product_service = AccountProductService(
            product_repo=self.product_accounts_repo,
            category_repo=self.categories_repo,
            storage_repo=self.account_storage_repo,
            accounts_cache_repo=self.accounts_cache_repo,
            accounts_cache_filler=self.accounts_cache_filler_service,
            category_filler_service=self.categories_cache_filler_service,
            session_db=self.session_db,
        )
        self.account_deleted_service = AccountDeletedService(
            deleted_repo=self.deleted_accounts_repo,
            session_db=self.session_db,
        )
        self.account_tg_media_service = AccountTgMediaService(
            tg_media_repo=self.tg_account_media_repo,
            session_db=self.session_db,
        )
        self.account_sold_service = AccountSoldService(
            sold_repo=self.sold_accounts_repo,
            translations_repo=self.sold_accounts_translation_repo,
            user_repo=self.users_repo,
            accounts_cache_repo=self.accounts_cache_repo,
            accounts_cache_filler=self.accounts_cache_filler_service,
            conf=self.config,
            session_db=self.session_db,
        )
        self.account_translations_service = AccountTranslationsService(
            sold_repo=self.sold_accounts_repo,
            translations_repo=self.sold_accounts_translation_repo,
            accounts_cache_filler=self.accounts_cache_filler_service,
            session_db=self.session_db,
        )

        self.product_universal_cache_repo = ProductUniversalCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.product_universal_single_cache_repo = ProductUniversalSingleCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.sold_universal_cache_repo = SoldUniversalCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.sold_universal_single_cache_repo = SoldUniversalSingleCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )

        self.universal_cache_filler_service = UniversalCacheFillerService(
            product_repo=self.product_universal_repo,
            sold_repo=self.sold_universal_repo,
            product_cache_repo=self.product_universal_cache_repo,
            product_single_cache_repo=self.product_universal_single_cache_repo,
            sold_cache_repo=self.sold_universal_cache_repo,
            sold_single_cache_repo=self.sold_universal_single_cache_repo,
            conf=self.config,
        )
        self.universal_deleted_service = UniversalDeletedService(
            deleted_repo=self.deleted_universal_repo,
            session_db=self.session_db,
        )
        self.universal_product_service = UniversalProductService(
            product_repo=self.product_universal_repo,
            storage_repo=self.universal_storage_repo,
            category_repo=self.categories_repo,
            product_cache_repo=self.product_universal_cache_repo,
            product_single_cache_repo=self.product_universal_single_cache_repo,
            cache_filler=self.universal_cache_filler_service,
            category_filler=self.categories_cache_filler_service,
            conf=self.config,
            session_db=self.session_db,
        )
        self.universal_storage_service = UniversalStorageService(
            storage_repo=self.universal_storage_repo,
            translation_repo=self.universal_translation_repo,
            cache_filler=self.universal_cache_filler_service,
            conf=self.config,
            session_db=self.session_db,
        )
        self.universal_sold_service = UniversalSoldService(
            sold_repo=self.sold_universal_repo,
            storage_repo=self.universal_storage_repo,
            user_repo=self.users_repo,
            sold_cache_repo=self.sold_universal_cache_repo,
            sold_single_cache_repo=self.sold_universal_single_cache_repo,
            cache_filler=self.universal_cache_filler_service,
            conf=self.config,
            session_db=self.session_db,
        )
        self.universal_translations_service = UniversalTranslationsService(
            storage_repo=self.universal_storage_repo,
            translation_repo=self.universal_translation_repo,
            cache_filler=self.universal_cache_filler_service,
            session_db=self.session_db,
        )

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
        self.voucher_activations_repo = VoucherActivationsRepository(
            session_db=session_db,
            config=self.config,
        )
        self.vouchers_cache__repo = VouchersCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.vouchers_repo = VouchersRepository(
            session_db=session_db,
            config=self.config,
        )
        self.voucher_service = VoucherService(
            vouchers_repo=self.vouchers_repo,
            voucher_activations_repo=self.voucher_activations_repo,
            users_repo=self.users_repo,
            user_log_repo=self.user_log_repo,
            wallet_transaction_repo=self.wallet_transaction_repo,
            admin_actions_repo=self.admin_actions_repo,
            cache_vouchers_repo=self.vouchers_cache__repo,
            cache_users_repo=self.users_cache_repo,
            publish_event_handler=self.publish_event_handler,
            conf=self.config,
            session_db=self.session_db,
        )

        self.promo_code_repo = PromoCodeRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.promo_code_cache_repo = PromoCodesCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.activated_promo_code_repo = ActivatedPromoCodeRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.activated_service = ActivatedPromoCodesService(activated_repo=self.activated_promo_code_repo)

        self.promo_code_service = PromoCodeService(
            promo_repo=self.promo_code_repo,
            admin_actions_repo=self.admin_actions_repo,
            cache_repo=self.promo_code_cache_repo,
            activate_promo_code_service=self.activated_service,
            user_log=self.user_log_service,
            conf=self.config,
            session_db=self.session_db,
        )

        self.referral_income_repo = ReferralIncomeRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.referral_income_service = ReferralIncomeService(
            income_repo=self.referral_income_repo,
        )

        self.referral_levels_repo = ReferralLevelsRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.referral_levels_cache_repo = ReferralLevelsCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.referral_levels_service = ReferralLevelsService(
            referral_lvl_repo=self.referral_levels_repo,
            cache_repo=self.referral_levels_cache_repo,
            session_db=self.session_db
        )

        self.referrals_repository = ReferralsRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.referral_service = ReferralService(
            referral_repo=self.referrals_repository,
            referral_income_service=self.referral_income_service,
            referral_lvls_service=self.referral_levels_service,
            log_service=self.user_log_service,
            user_service=self.user_service,
            wallet_transaction_service=self.wallet_transaction_service,
            session_db=self.session_db
        )

        self.excel_report_exporter = ExcelReportExporter(
            get_text=get_text,
            dt_format=self.config.different.dt_format,
        )

        self.type_payment_repo = TypePaymentsRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.type_payment_cache_repo = TypePaymentsCacheRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.type_payments_service = TypesPaymentsService(
            type_payment_repo=self.type_payment_repo,
            cache_repo=self.type_payment_cache_repo,
            session_db=self.session_db
        )

        self.dollar_rate_repo = DollarRateRepository(
            redis_session=self.session_redis,
            config=self.config,
        )
        self.payment_service = PaymentService(
            replenishments_service=self.replenishment_service,
            publish_event_handler=self.publish_event_handler,
            types_payments_service=self.type_payments_service,
            user_service=self.user_service,
            dollar_rate_repo=self.dollar_rate_repo,
            crypto_provider=crypto_bot_provider,
            conf=self.config,
            logger=self.logger,
        )

    def get_message_service(self,) -> Messages:
        rate_limiter = RateLimiter(
            max_calls=self.config.different.rate_send_msg_limit,
            period=1.0,
        )
        sticker_sender = StickerSender(
            tg_client=self.telegram_client,
            sticker_service=self.stickers_service,
            publish_event_handler=self.publish_event_handler
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
            logger=self.logger,
            user_service=self.user_service,
            permission_service=self.permission_service,
            wallet_transaction_service=self.wallet_transaction_service,
            money_transfer_service=self.money_transfer_service,
            notification_service=self.notification_service,
            voucher_service=self.voucher_service,
            referral_income_service=self.referral_income_service,
            referral_levels_service=self.referral_levels_service,
            referral_service=self.referral_service,
            excel_report_exporter=self.excel_report_exporter,
            type_payments_service=self.type_payments_service,
            payment_service=self.payment_service,
            settings_service=self.settings_service,
            account_moduls=self.get_account_modul(),
            universal_moduls=self.get_universal_product_modul(),
        )

    def get_account_modul(self) -> AccountsModuls:
        return AccountsModuls(
            deleted_service=self.account_deleted_service,
            product_service=self.account_product_service,
            sold_service=self.account_sold_service,
            storage_service=self.account_storage_service,
            tg_media_service=self.account_tg_media_service,
            translations_service=self.account_translations_service,
            cache_filler_service=self.accounts_cache_filler_service,
            conf=self.config,
            logger=self.logger,
        )

    def get_universal_product_modul(self) -> UniversalModuls:
        return UniversalModuls(
            deleted_service=self.universal_deleted_service,
            product_service=self.universal_product_service,
            sold_service=self.universal_sold_service,
            storage_service=self.universal_storage_service,
            translations_service=self.universal_translations_service,
            cache_filler_service=self.universal_cache_filler_service,
            conf=self.config,
            logger=self.logger,
        )

    def get_cache_warmup_service(self) -> CacheWarmupService:
        return CacheWarmupService(
            settings_repo=self.settings_repo,
            stickers_repo=self.stickers_repo,
            referral_levels_repo=self.referral_levels_repo,
            type_payments_repo=self.type_payment_repo,
            admins_repo=self.admin_repo,
            banned_accounts_repo=self.banned_accounts_repo,
            categories_repo=self.categories_repo,
            product_accounts_repo=self.product_accounts_repo,
            sold_accounts_repo=self.sold_accounts_repo,
            product_universal_repo=self.product_universal_repo,
            sold_universal_repo=self.sold_universal_repo,
            users_repo=self.users_repo,
            promo_codes_repo=self.promo_code_repo,
            ui_image_repo=self.ui_image_repo,
            vouchers_repo=self.vouchers_repo,

            settings_cache_repo=self.settings_cache_repo,
            stickers_cache_repo=self.stickers_cache_repo,
            referral_levels_cache_repo=self.referral_levels_cache_repo,
            type_payments_cache_repo=self.type_payment_cache_repo,
            admins_cache_repo=self.admin_cache_repo,
            banned_accounts_cache_repo=self.banned_accounts_cache_repo,
            categories_cache_repo=self.categories_cache_repo,
            promo_codes_cache_repo=self.promo_code_cache_repo,
            vouchers_cache_repo=self.vouchers_cache__repo,
            ui_images_cache_repo=self.ui_images_cache_repo,
            accounts_cache_repo=self.accounts_cache_repo,
            sold_universal_cache_repo=self.sold_universal_cache_repo,
            sold_universal_single_cache_repo=self.sold_universal_single_cache_repo,
            category_cache_filler_service=self.categories_cache_filler_service,

            accounts_cache_filler_service=self.accounts_cache_filler_service,
            universal_cache_filler_service=self.universal_cache_filler_service,
            logger=self.logger,
            conf=self.config,
        )

    def get_event_handler(self) -> EventHandler:
        messages = self.get_message_service()

        return EventHandler(
            promo_code_ev_hand=PromoCodeEventHandler(
                publish_event=self.publish_event_handler,
                promo_code_service=self.promo_code_service,
                session_db=self.session_db,
            ),
            referral_ev_hand=ReferralEventHandler(
                publish_event=self.publish_event_handler,
                referral_service=self.referral_service,
                notification_service=self.notification_service,
                send_msg_service=messages.send_msg,
            ),
            replenishment_ev_hand=ReplenishmentsEventHandler(
                publish_event=self.publish_event_handler,
                replenishment_service=self.replenishment_service,
                send_msg_service=messages.send_msg,
            ),
            purchase_ev_hand=PurchaseEventHandler(
                publish_event=self.publish_event_handler,
                user_log_service=self.user_log_service,
                wallet_trans_service=self.wallet_transaction_service,
                session_db=self.session_db,
            ),
            filesystem_ev_hand=FileSystemEventHandler(
                path_builder=self.path_builder,
                ui_image_service=self.ui_images_service,
                logger=self.logger,
            ),
            message_ev_hand=MessageEventHandler(
                send_log=messages.send_log,
            ),
            logger=self.logger,
        )


def init_request_container(
    session_db: AsyncSession,
    telegram_client: "TelegramClient",
    telegram_logger_client: "TelegramClient",
    crypto_bot_provider: CryptoBotProvider,
) -> RequestContainer:
    return RequestContainer(session_db, telegram_client, telegram_logger_client, crypto_bot_provider)
