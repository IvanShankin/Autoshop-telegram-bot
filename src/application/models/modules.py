from logging import Logger

from src.application.cache_warmup import CacheWarmupService
from src.application.crypto.crypto_context import CryptoProvider
from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.admins import AdminsService
from src.application.models.categories import CategoryService
from src.application.models.purchases import PurchaseService
from src.application.models.users.pubscription_prompt import SubscriptionService
from src.application.products.accounts.account_service import AccountService
from src.config import Config
from src.infrastructure.files.excel_reports import ExcelReportExporter
from src.application.models.discounts import VoucherService, PromoCodeService
from src.application.models.payment_services import PaymentService
from src.application.models.products.accounts import AccountDeletedService, AccountProductService, AccountSoldService, \
    AccountStorageService, AccountTgMediaService, AccountTranslationsService, AccountsCacheFillerService
from src.application.models.products.universal import UniversalDeletedService, UniversalProductService, \
    UniversalSoldService, UniversalStorageService, UniversalTranslationsService, UniversalCacheFillerService
from src.application.models.referrals import ReferralService, ReferralIncomeService, ReferralLevelsService
from src.application.models.systems import TypesPaymentsService, SettingsService, UiImagesService
from src.application.models.users import WalletTransactionService, UserService, MoneyTransferService, \
    NotificationSettingsService, BannedAccountService
from src.application.models.users.permission_service import PermissionService
from src.infrastructure.files.path_builder import PathBuilder


class AccountsModuls:

    def __init__(
        self,
        deleted_service: AccountDeletedService,
        product_service: AccountProductService,
        sold_service: AccountSoldService,
        storage_service: AccountStorageService,
        tg_media_service: AccountTgMediaService,
        translations_service: AccountTranslationsService,
        cache_filler_service: AccountsCacheFillerService,
        conf: Config,
        logger: Logger,
    ):
        self.deleted_service = deleted_service
        self.product_service = product_service
        self.sold_service = sold_service
        self.storage_service = storage_service
        self.tg_media_service = tg_media_service
        self.translations_service = translations_service
        self.cache_filler_service = cache_filler_service
        self.conf = conf
        self.logger = logger


class UniversalModuls:

    def __init__(
        self,
        deleted_service: UniversalDeletedService,
        product_service: UniversalProductService,
        sold_service: UniversalSoldService,
        storage_service: UniversalStorageService,
        translations_service: UniversalTranslationsService,
        cache_filler_service: UniversalCacheFillerService,
        conf: Config,
        logger: Logger,
    ):
        self.deleted_service = deleted_service
        self.product_service = product_service
        self.sold_service = sold_service
        self.storage_service = storage_service
        self.translations_service = translations_service
        self.cache_filler_service = cache_filler_service
        self.conf = conf
        self.logger = logger


class ProfileModule:

    def __init__(
        self,
        conf: Config,
        logger: Logger,
        user_service: UserService,
        permission_service: PermissionService,
        wallet_transaction_service: WalletTransactionService,
        money_transfer_service: MoneyTransferService,
        notification_service: NotificationSettingsService,
        voucher_service: VoucherService,
        referral_income_service: ReferralIncomeService,
        referral_levels_service: ReferralLevelsService,
        referral_service: ReferralService,
        excel_report_exporter: ExcelReportExporter,
        type_payments_service: TypesPaymentsService,
        payment_service: PaymentService,
        settings_service: SettingsService,
        account_moduls: AccountsModuls,
        universal_moduls: UniversalModuls,
        account_service: AccountService,
        crypto_provider: CryptoProvider,
        path_builder: PathBuilder,
    ):
        self.conf = conf
        self.logger = logger
        self.user_service = user_service
        self.permission_service = permission_service
        self.wallet_transaction_service = wallet_transaction_service
        self.money_transfer_service = money_transfer_service
        self.notification_service = notification_service
        self.voucher_service = voucher_service
        self.referral_income_service = referral_income_service
        self.referral_levels_service = referral_levels_service
        self.referral_service = referral_service
        self.excel_report_exporter = excel_report_exporter
        self.type_payments_service = type_payments_service
        self.payment_service = payment_service
        self.settings_service = settings_service
        self.account_moduls = account_moduls
        self.universal_moduls = universal_moduls
        self.account_service = account_service
        self.crypto_provider = crypto_provider
        self.path_builder = path_builder


class CatalogModule:

    def __init__(
        self,
        conf: Config,
        logger: Logger,
        user_service: UserService,
        purchase_service: PurchaseService,
        category_service: CategoryService,
        promo_code_service: PromoCodeService,
        subscription_service: SubscriptionService,
        settings_service: SettingsService,
        ui_image_service: UiImagesService,
        account_sold_service: AccountSoldService,
        universal_sold_service: UniversalSoldService,
    ):
        self.conf = conf
        self.logger = logger
        self.user_service = user_service
        self.purchase_service = purchase_service
        self.category_service = category_service
        self.promo_code_service = promo_code_service
        self.subscription_service = subscription_service
        self.settings_service = settings_service
        self.ui_image_service = ui_image_service
        self.account_sold_service = account_sold_service
        self.universal_sold_service = universal_sold_service


class AdminModule:

    def __init__(
        self,
        conf: Config,
        logger: Logger,
        user_service: UserService,
        permission_service: PermissionService,
        wallet_transaction_service: WalletTransactionService,
        money_transfer_service: MoneyTransferService,
        notification_service: NotificationSettingsService,
        voucher_service: VoucherService,
        referral_income_service: ReferralIncomeService,
        referral_levels_service: ReferralLevelsService,
        referral_service: ReferralService,
        excel_report_exporter: ExcelReportExporter,
        type_payments_service: TypesPaymentsService,
        payment_service: PaymentService,
        settings_service: SettingsService,
        account_moduls: AccountsModuls,
        universal_moduls: UniversalModuls,
        account_service: AccountService,
        admin_service: AdminsService,
        banned_account_service: BannedAccountService,
        crypto_provider: CryptoProvider,
        publish_event_handler: PublishEventHandler,
        cache_warmup_service: CacheWarmupService,
        path_builder: PathBuilder,
    ):
        self.conf = conf
        self.logger = logger
        self.user_service = user_service
        self.permission_service = permission_service
        self.wallet_transaction_service = wallet_transaction_service
        self.money_transfer_service = money_transfer_service
        self.notification_service = notification_service
        self.voucher_service = voucher_service
        self.referral_income_service = referral_income_service
        self.referral_levels_service = referral_levels_service
        self.referral_service = referral_service
        self.excel_report_exporter = excel_report_exporter
        self.type_payments_service = type_payments_service
        self.payment_service = payment_service
        self.settings_service = settings_service
        self.account_moduls = account_moduls
        self.universal_moduls = universal_moduls
        self.account_service = account_service
        self.admin_service = admin_service
        self.banned_account_service = banned_account_service
        self.crypto_provider = crypto_provider
        self.publish_event_handler = publish_event_handler
        self.cache_warmup_service = cache_warmup_service
        self.path_builder = path_builder