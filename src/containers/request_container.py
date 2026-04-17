from typing import TYPE_CHECKING, Optional, Callable, Awaitable, Any

from aiohttp import ClientSession
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.crypto.crypto_context import CryptoProvider
from src.application.currenccy.update_dollare_rate import UpdateDollarRateUseCase
from src.application.models.discounts.remove_invalid import RemoveInvalidDiscountsUseCase
from src.application.models.systems.backup_db_service import BackupDBService
from src.application.models.users.use_cases import GenerateUserAuditLogUseCase
from src.application.payments.crypto_bot.use_cases.process_webhook import ProcessCryptoWebhookUseCase
from src.application.products.accounts.account_service import AccountService
from src.application.products.accounts.generate_exampl_import import GenerateExamplImportAccount
from src.application.products.accounts.other.use_cases import UploadOtherAccountsUseCase, ImportOtherAccountsUseCase
from src.application.products.accounts.other.use_cases.validate import ValidateOtherAccountsUseCase
from src.application.products.accounts.tg.use_cases import ImportTelegramAccountsUseCase, UploadTGAccountsUseCase
from src.application.products.accounts.tg.use_cases.get_auth_codes import GetAuthCodesUseCase
from src.application.products.accounts.tg.use_cases.validate import ValidateTgAccount
from src.application.products.universals.universal_products import UniversalProduct
from src.application.products.universals.use_cases import ValidationsUniversalProducts, \
    GenerateExamplUniversalProductImport, UploadUniversalProductsUseCase, ImportUniversalProductUseCase
from src.config import get_config
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage
from src.infrastructure.crypto_bot.core import CryptoBotProvider
from src.infrastructure.currency.cbr_client import CBRClient
from src.infrastructure.currency.moex_client import MoexClient
from src.infrastructure.files.excel_reports import ExcelReportExporter
from src.infrastructure.files.file_system import FileStorage
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.telegram.account_client import TelegramAccountClient
from src.infrastructure.telegram.rate_limit import RateLimiter
from src.repository.database.discount import VouchersRepository, VoucherActivationsRepository, PromoCodeRepository, \
    ActivatedPromoCodeRepository
from src.repository.database.referrals import ReferralsRepository, ReferralIncomeRepository, ReferralLevelsRepository
from src.repository.database.replanishments import ReplenishmentsRepository
from src.application.cache_warmup import CacheWarmupService
from src.application.events.event_handlers.file_system import FileSystemEventHandler
from src.application.events.event_handlers.main_event_handler import EventHandler
from src.application.events.event_handlers.message import MessageEventHandler
from src.application.events.event_handlers.promo_code import PromoCodeEventHandler
from src.application.events.event_handlers.purchase import PurchaseEventHandler
from src.application.events.event_handlers.referrals import ReferralEventHandler
from src.application.events.event_handlers.replenishments import ReplenishmentsEventHandler
from src.application.models.discounts import ActivatedPromoCodesService, PromoCodeService, VoucherActivationsService
from src.application.models.discounts.vouchers_service import VoucherService
from src.application.models.categories.category_service import CategoryService
from src.application.models.categories.category_translate_service import TranslationsCategoryService
from src.application.models.purchases.purchase_service import PurchaseService
from src.application.models.purchases.accounts.account_purchase_service import AccountPurchaseService
from src.application.models.purchases.general.purchase_cancel_service import PurchaseCancelService
from src.application.models.purchases.general.purchase_request_service import PurchaseRequestService
from src.application.models.purchases.general.purchase_validation_service import PurchaseValidationService
from src.application.models.purchases.universal.universal_purchase_service import UniversalPurchaseService
from src.application.models.users.pubscription_prompt import SubscriptionService
from src.application.models.modules import ProfileModule, AccountsModuls, UniversalModuls, CatalogModule, AdminModule
from src.repository.database.admins import (
    AdminActionsRepository,
    AdminsRepository,
    MessageForSendingRepository, SentMasMessagesRepository,
)
from src.repository.database.base import DatabaseBase
from src.repository.database.categories import (
    CategoriesRepository,
    CategoryTranslationsRepository,
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
    PurchaseRequestsRepository,
    PurchaseRequestAccountsRepository,
    PurchaseRequestUniversalRepository,
    PurchasesRepository,
)
from src.repository.database.systems import (
    StickersRepository,
    UiImagesRepository, FilesRepository, SettingsRepository, TypePaymentsRepository, BackupLogsRepository,
)
from src.repository.database.users import (
    BannedAccountsRepository,
    BalanceHolderRepository,
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
    ReferralLevelsCacheRepository, TypePaymentsCacheRepository, DollarRateCacheRepository,
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
    TypesPaymentsService, BackupLogsService, StatisticsService, EventMessageService
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
    from src.infrastructure.telegram.bot_client import TelegramClient


class RequestContainer:
    """
    Контейнер для сборки сервисного слоя. Вызывается строго только в middleware!
    """

    def __init__(
        self,
        session_db: AsyncSession,
        session_redis: Redis,
        http_session: ClientSession,
        telegram_client : "TelegramClient",
        telegram_logger_client: "TelegramClient",
        crypto_bot_provider: CryptoBotProvider,
        crypto_provider: CryptoProvider,
        secret_storage: SecretsStorage,
        support_kb_builder: Callable[[str, str], Awaitable[Any]],
        telegram_account_client: TelegramAccountClient,
    ):
        self.session_db = session_db
        self.session_redis = session_redis
        self.http_session = http_session
        self.telegram_client = telegram_client
        self.telegram_logger_client = telegram_logger_client

        self.crypto_provider = crypto_provider
        self.secret_storage = secret_storage
        self.support_kb_builder = support_kb_builder
        self.telegram_account_client = telegram_account_client

        self.account_sold_service: Optional[AccountSoldService] = None

        self.config = get_config()
        self.logger = get_logger(__name__)
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
            path_builder=self.path_builder,
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
            ui_image_service=self.ui_images_service,
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
        self.category_translations_repo = CategoryTranslationsRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.translations_category_service = TranslationsCategoryService(
            category_translations_repo=self.category_translations_repo,
            category_repo=self.categories_repo,
            category_cache_repo=self.categories_cache_repo,
            category_filler_service=self.categories_cache_filler_service,
            session_db=self.session_db,
        )
        self.category_service = CategoryService(
            category_repo=self.categories_repo,
            category_cache_repo=self.categories_cache_repo,
            product_accounts_repository=self.product_accounts_repo,
            translations_category_service=self.translations_category_service,
            category_filler_service=self.categories_cache_filler_service,
            ui_image_cache_repo=self.ui_images_cache_repo,
            ui_image_service=self.ui_images_service,
            session_db=self.session_db,
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
            path_builder=self.path_builder,
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
            path_builder=self.path_builder,
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
            publish_event_handler=self.publish_event_handler,
            conf=self.config,
            session_db=self.session_db,
        )

        self.account_service = AccountService(
            publish_event_handler=self.publish_event_handler,
            path_builder=self.path_builder,
            crypto_provider=self.crypto_provider,
            logger=self.logger,
        )

        self.purchase_requests_repo = PurchaseRequestsRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.balance_holder_repo = BalanceHolderRepository(
            session_db=self.session_db,
            config=self.config,
        )
        self.purchase_request_service = PurchaseRequestService(
            purchase_request_repo=self.purchase_requests_repo,
            balance_holder_repo=self.balance_holder_repo,
            users_repo=self.users_repo,
        )
        self.purchase_cancel_service = PurchaseCancelService(
            purchase_request_service=self.purchase_request_service,
            logger=self.logger,
        )
        self.purchase_validation_service = PurchaseValidationService(
            categories_repo=self.categories_repo,
            users_repo=self.users_repo,
            promo_code_service=self.promo_code_service,
            conf=self.config,
        )
        self.validate_tg_account = ValidateTgAccount(
            logger=self.logger,
            tg_client=self.telegram_account_client,
            crypto_provider=self.crypto_provider,
            account_service=self.account_service,
        )
        self.validate_other_account = ValidateOtherAccountsUseCase(
            logger=self.logger,
            crypto_provider=self.crypto_provider,
        )
        self.purchases_repo = PurchasesRepository(
                session_db=self.session_db,
                config=self.config,
            )
        self.account_purchase_service = AccountPurchaseService(
            validation_service=self.purchase_validation_service,
            purchase_request_service=self.purchase_request_service,
            purchase_cancel_service=self.purchase_cancel_service,
            product_repo=self.product_accounts_repo,
            storage_repo=self.account_storage_repo,
            purchase_request_account_repo=PurchaseRequestAccountsRepository(
                session_db=self.session_db,
                config=self.config,
            ),
            sold_repo=self.sold_accounts_repo,
            sold_trans_repo=self.sold_accounts_translation_repo,
            purchases_repo=self.purchases_repo,
            deleted_service=self.account_deleted_service,
            category_service=self.category_service,
            accounts_cache_filler=self.accounts_cache_filler_service,
            categories_cache_filler=self.categories_cache_filler_service,
            user_cache_repo=self.users_cache_repo,
            account_service=self.account_service,
            path_build=self.path_builder,
            publish_event_handler=self.publish_event_handler,
            logger=self.logger,
            conf=self.config,
            session_db=self.session_db,
            validate_tg_account=self.validate_tg_account,
            validate_other_account=self.validate_other_account,
        )
        self.validations_universal_products = ValidationsUniversalProducts(
            crypto_provider=self.crypto_provider,
            path_builder=self.path_builder,
            logger=self.logger,
        )
        self.universal_product = UniversalProduct(
            crypto_provider=self.crypto_provider,
            path_builder=self.path_builder,
            publish_event_handler=self.publish_event_handler,
            logger=self.logger,
        )
        self.universal_purchase_service = UniversalPurchaseService(
            validation_service=self.purchase_validation_service,
            purchase_request_service=self.purchase_request_service,
            purchase_cancel_service=self.purchase_cancel_service,
            product_repo=self.product_universal_repo,
            storage_repo=self.universal_storage_repo,
            purchase_request_universal_repo=PurchaseRequestUniversalRepository(
                session_db=self.session_db,
                config=self.config,
            ),
            sold_repo=self.sold_universal_repo,
            purchases_repo=self.purchases_repo,
            deleted_service=self.universal_deleted_service,
            category_service=self.category_service,
            cache_filler=self.universal_cache_filler_service,
            categories_cache_filler=self.categories_cache_filler_service,
            user_cache_repo=self.users_cache_repo,
            publish_event_handler=self.publish_event_handler,
            path_builder=self.path_builder,
            validations_universal_products=self.validations_universal_products,
            universal_product=self.universal_product,
            crypto_provider=self.crypto_provider,
            conf=self.config,
            logger=self.logger,
            session_db=self.session_db,
        )
        self.subscription_service = SubscriptionService(
            subscription_cache_repo=self.subscription_cache_repo,
            conf=self.config,
        )
        self.purchase_service = PurchaseService(
            account_purchase_service=self.account_purchase_service,
            universal_purchase_service=self.universal_purchase_service,
            categories_cache_filler=self.categories_cache_filler_service,
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

        self.dollar_rate_repo = DollarRateCacheRepository(
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

        self.backup_logs_repository = BackupLogsRepository(
            session_db=self.session_db,
            config=self.config,
        )

        self.backup_logs_service = BackupLogsService(
            backup_logs_repo=self.backup_logs_repository,
            session_db=self.session_db
        )
        self.import_tg_account_use_case = ImportTelegramAccountsUseCase(
            account_storage_service=self.account_storage_service,
            account_service=self.account_service,
            account_product_service=self.account_product_service,
            path_builder=self.path_builder,
            tg_client=self.telegram_account_client,
            logger=self.logger
        )
        self.upload_tg_account_use_case = UploadTGAccountsUseCase(
            account_service=self.account_service,
            account_product_service=self.account_product_service,
            conf=self.config,
            crypto_provider=self.crypto_provider,
        )
        self.import_other_account_use_case = ImportOtherAccountsUseCase(
            account_storage_service=self.account_storage_service,
            account_product_service=self.account_product_service,
            crypto_provider=self.crypto_provider,
            publish_event_handler=self.publish_event_handler,
            logger=self.logger,
        )
        self.upload_other_accounts_use_case = UploadOtherAccountsUseCase(
            account_product_service=self.account_product_service,
            logger=self.logger,
            crypto_provider=self.crypto_provider,
            publish_event_handler=self.publish_event_handler,
        )
        self.generate_exampl_universal_product_import = GenerateExamplUniversalProductImport(
            conf=self.config,
        )
        self.upload_universal_products_use_case = UploadUniversalProductsUseCase(
            path_builder=self.path_builder,
            crypto_provider=self.crypto_provider,
            universal_product_service=self.universal_product_service,
            universal_translations_service=self.universal_translations_service,
            logger=self.logger,
            conf=self.config,
        )
        self.import_universal_product_use_case = ImportUniversalProductUseCase(
            path_builder=self.path_builder,
            crypto_provider=self.crypto_provider,
            universal_product_service=self.universal_product_service,
            universal_translations_service=self.universal_translations_service,
            universal_storage_service=self.universal_storage_service,
            translations_category_service=self.translations_category_service,
            logger=self.logger,
            conf=self.config,
        )
        self.statistics_service = StatisticsService(
            type_payments_repo=self.type_payment_repo,
            session_db=self.session_db,
        )
        self.voucher_activations_service = VoucherActivationsService(
            activations_repo=self.voucher_activations_repo
        )
        self.activated_promo_codes_service = ActivatedPromoCodesService(
            activated_repo=self.activated_promo_code_repo
        )
        self.generate_user_audit_log_use_case = GenerateUserAuditLogUseCase(
            conf=self.config,
            user_log_service=self.user_log_service,
        )
        self.generate_example_import_account = GenerateExamplImportAccount(
            conf=self.config,
        )
        self. event_message_service = EventMessageService(
            conf=self.config,
        )
        self.get_auth_codes_use_case = GetAuthCodesUseCase(
            tg_client=self.telegram_account_client,
            crypto_provider=self.crypto_provider,
            account_service=self.account_service,
            logger=self.logger,
        )
        self.process_crypto_webhook_use_case = ProcessCryptoWebhookUseCase(
            replenishment_service=self.replenishment_service,
            publish_event_handler=self.publish_event_handler,
            logger=self.logger,
        )
        self.update_dollar_rate_use_case = UpdateDollarRateUseCase(
            moex_client=MoexClient(
                session=self.http_session,
                logger=self.logger,
            ),
            cbr_client=CBRClient(
                session=self.http_session,
                logger=self.logger,
            ),
            dollar_rate_repo=DollarRateCacheRepository(
                redis_session=self.session_redis,
                config=self.config,
            ),
            logger=self.logger
        )

    def get_backup_db(self):
        return BackupDBService(
            conf=self.config,
            logger=self.logger,
            crypto_provider=self.crypto_provider,
            secret_storage=self.secret_storage,
            backup_logs_service=self.backup_logs_service,
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
            account_service=self.account_service,
            crypto_provider=self.crypto_provider,
            path_builder=self.path_builder,
            get_auth_codes_use_case=self.get_auth_codes_use_case,
            validate_tg_account=self.validate_tg_account,
        )

    def get_catalog_modul(self) -> CatalogModule:
        return CatalogModule(
            conf=self.config,
            logger=self.logger,
            user_service=self.user_service,
            purchase_service=self.purchase_service,
            category_service=self.category_service,
            promo_code_service=self.promo_code_service,
            subscription_service=self.subscription_service,
            settings_service=self.settings_service,
            ui_image_service=self.ui_images_service,
            account_sold_service=self.account_sold_service,
            universal_sold_service=self.universal_sold_service,
        )

    def get_admin_module(self) -> AdminModule:
        return AdminModule(
            conf=self.config,
            logger=self.logger,
            user_service=self.user_service,
            permission_service=self.permission_service,
            wallet_transaction_service=self.wallet_transaction_service,
            money_transfer_service=self.money_transfer_service,
            notification_service=self.notification_service,
            voucher_service=self.voucher_service,
            voucher_activations_service=self.voucher_activations_service,
            promo_code_service=self.promo_code_service,
            activated_promo_codes_service=self.activated_promo_codes_service,
            referral_income_service=self.referral_income_service,
            referral_levels_service=self.referral_levels_service,
            referral_service=self.referral_service,
            excel_report_exporter=self.excel_report_exporter,
            type_payments_service=self.type_payments_service,
            payment_service=self.payment_service,
            settings_service=self.settings_service,
            account_moduls=self.get_account_modul(),
            universal_moduls=self.get_universal_product_modul(),
            account_service=self.account_service,
            admin_service=self.admin_service,
            banned_account_service=self.banned_account_service,
            crypto_provider=self.crypto_provider,
            publish_event_handler=self.publish_event_handler,
            cache_warmup_service=self.get_cache_warmup_service(),
            statistics_service=self.statistics_service,
            replenishments_service=self.replenishment_service,
            purchases_repo=self.purchases_repo,
            path_builder=self.path_builder,
            generate_user_audit_log_use_case=self.generate_user_audit_log_use_case,
            category_service=self.category_service,
            translations_category_service=self.translations_category_service,
            ui_images_service=self.ui_images_service,
            upload_universal_products_use_case=self.upload_universal_products_use_case,
            upload_tg_account_use_case=self.upload_tg_account_use_case,
            upload_other_account_use_case=self.upload_other_accounts_use_case,
            generate_example_import_account=self.generate_example_import_account,
            generate_exampl_universal_import=self.generate_exampl_universal_product_import,
            import_tg_account=self.import_tg_account_use_case,
            import_other_account=self.import_other_account_use_case,
            import_universal_product=self.import_universal_product_use_case,
            event_message_service=self.event_message_service,
            sent_mass_message_service=self.sent_mass_message_service,
            message_for_sending_service=self.msg_for_sending_service,
            stickers_service=self.stickers_service,
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
            universal_product=self.universal_product,
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
            session_redis=self.session_redis,
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
                settings_service=self.settings_service,
                send_msg_service=messages.send_msg,
                logger=self.logger,
                conf=self.config,
                support_kb_builder=self.support_kb_builder,
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

    def get_remove_invalid_discount_use_case(self) -> RemoveInvalidDiscountsUseCase:
        return RemoveInvalidDiscountsUseCase(
            user_service=self.user_service,
            promo_code_repo=self.promo_code_repo,
            promo_code_service=self.promo_code_service,
            voucher_repo=self.vouchers_repo,
            voucher_service=self.voucher_service,
            publish_event_handler=self.publish_event_handler,
            tg_client=self.get_tg_client(),
            logger=self.logger,
        )

    def get_tg_client(self) -> "TelegramClient":
        return self.telegram_client

    def get_tg_logger_client(self) -> "TelegramClient":
        return self.telegram_logger_client


def init_request_container(
    session_db: AsyncSession,
    session_redis: Redis,
    http_session: ClientSession,
    telegram_client: "TelegramClient",
    telegram_logger_client: "TelegramClient",
    crypto_bot_provider: CryptoBotProvider,
    crypto_provider: CryptoProvider,
    secret_storage: SecretsStorage,
    support_kb_builder: Callable[[str, str], Awaitable[Any]],
    telegram_account_client: TelegramAccountClient,
) -> RequestContainer:
    return RequestContainer(
        session_db=session_db,
        session_redis=session_redis,
        http_session=http_session,
        telegram_client=telegram_client,
        telegram_logger_client=telegram_logger_client,
        crypto_bot_provider=crypto_bot_provider,
        crypto_provider=crypto_provider,
        secret_storage=secret_storage,
        support_kb_builder=support_kb_builder,
        telegram_account_client=telegram_account_client,
    )
