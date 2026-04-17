from logging import Logger

from src.application.bot import MassTgMailingService
from src.application.cache_warmup import CacheWarmupService
from src.application.crypto.crypto_context import CryptoProvider
from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.admins import AdminsService, SentMassMessagesService, MessageForSendingService
from src.application.models.categories import CategoryService, TranslationsCategoryService
from src.application.models.purchases import PurchaseService
from src.application.models.users.pubscription_prompt import SubscriptionService
from src.application.models.users.use_cases import GenerateUserAuditLogUseCase
from src.application.products.accounts.account_service import AccountService
from src.application.products.accounts.generate_exampl_import import GenerateExamplImportAccount
from src.application.products.accounts.other.use_cases import UploadOtherAccountsUseCase, ImportOtherAccountsUseCase
from src.application.products.accounts.tg.use_cases import UploadTGAccountsUseCase, ImportTelegramAccountsUseCase, \
    ValidateTgAccount
from src.application.products.accounts.tg.use_cases.get_auth_codes import GetAuthCodesUseCase
from src.application.products.universals.universal_products import UniversalProduct
from src.application.products.universals.use_cases import UploadUniversalProductsUseCase, \
    GenerateExamplUniversalProductImport, ImportUniversalProductUseCase
from src.config import Config
from src.infrastructure.files.excel_reports import ExcelReportExporter
from src.application.models.discounts import VoucherService, PromoCodeService, VoucherActivationsService, \
    ActivatedPromoCodesService
from src.application.models.payment_services import PaymentService
from src.application.models.products.accounts import AccountDeletedService, AccountProductService, AccountSoldService, \
    AccountStorageService, AccountTgMediaService, AccountTranslationsService, AccountsCacheFillerService
from src.application.models.products.universal import UniversalDeletedService, UniversalProductService, \
    UniversalSoldService, UniversalStorageService, UniversalTranslationsService, UniversalCacheFillerService
from src.application.models.referrals import ReferralService, ReferralIncomeService, ReferralLevelsService
from src.application.models.systems import TypesPaymentsService, SettingsService, UiImagesService, StatisticsService, \
    EventMessageService, StickersService
from src.application.models.users import WalletTransactionService, UserService, MoneyTransferService, \
    NotificationSettingsService, BannedAccountService, ReplenishmentsService
from src.application.models.users.permission_service import PermissionService
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.telegram.account_client import TelegramAccountClient
from src.repository.database.categories import PurchasesRepository


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
        universal_product: UniversalProduct,
        conf: Config,
        logger: Logger,
    ):
        self.deleted_service = deleted_service
        self.product_service = product_service
        self.sold_service = sold_service
        self.storage_service = storage_service
        self.translations_service = translations_service
        self.cache_filler_service = cache_filler_service
        self.universal_product = universal_product
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
        get_auth_codes_use_case: GetAuthCodesUseCase,
        validate_tg_account: ValidateTgAccount,
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
        self.get_auth_codes_use_case = get_auth_codes_use_case
        self.validate_tg_account = validate_tg_account


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
        voucher_activations_service: VoucherActivationsService,
        promo_code_service: PromoCodeService,
        activated_promo_codes_service: ActivatedPromoCodesService,
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
        statistics_service: StatisticsService,
        replenishments_service: ReplenishmentsService,
        purchases_repo: PurchasesRepository,
        path_builder: PathBuilder,
        generate_user_audit_log_use_case: GenerateUserAuditLogUseCase,
        category_service: CategoryService,
        translations_category_service: TranslationsCategoryService,
        ui_images_service: UiImagesService,
        upload_universal_products_use_case: UploadUniversalProductsUseCase,
        upload_tg_account_use_case: UploadTGAccountsUseCase,
        upload_other_account_use_case: UploadOtherAccountsUseCase,
        generate_example_import_account: GenerateExamplImportAccount,
        generate_exampl_universal_import: GenerateExamplUniversalProductImport,
        import_tg_account: ImportTelegramAccountsUseCase,
        import_other_account: ImportOtherAccountsUseCase,
        import_universal_product: ImportUniversalProductUseCase,
        event_message_service: EventMessageService,
        sent_mass_message_service: SentMassMessagesService,
        message_for_sending_service: MessageForSendingService,
        stickers_service: StickersService,
    ):
        self.conf = conf
        self.logger = logger
        self.user_service = user_service
        self.permission_service = permission_service
        self.wallet_transaction_service = wallet_transaction_service
        self.money_transfer_service = money_transfer_service
        self.notification_service = notification_service
        self.voucher_service = voucher_service
        self.voucher_activations_service = voucher_activations_service
        self.promo_code_service = promo_code_service
        self.activated_promo_codes_service = activated_promo_codes_service
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
        self.statistics_service = statistics_service
        self.replenishments_service = replenishments_service
        self.purchases_repo = purchases_repo
        self.path_builder = path_builder
        self.generate_user_audit_log_use_case = generate_user_audit_log_use_case
        self.category_service = category_service
        self.translations_category_service = translations_category_service
        self.ui_images_service = ui_images_service
        self.upload_universal_products_use_case = upload_universal_products_use_case
        self.upload_tg_account_use_case = upload_tg_account_use_case
        self.upload_other_account_use_case = upload_other_account_use_case
        self.generate_example_import_account = generate_example_import_account
        self.generate_exampl_universal_import = generate_exampl_universal_import
        self.import_tg_account = import_tg_account
        self.import_other_account = import_other_account
        self.import_universal_product = import_universal_product
        self.event_message_service = event_message_service
        self.sent_mass_message_service = sent_mass_message_service
        self.message_for_sending_service = message_for_sending_service
        self.stickers_service = stickers_service