from logging import Logger

from src.config import Config
from src.infrastructure.files.excel_reports import ExcelReportExporter
from src.services.models.discounts import VoucherService
from src.services.models.payment_services import PaymentService
from src.services.models.referrals import ReferralService, ReferralIncomeService, ReferralLevelsService
from src.services.models.systems import TypesPaymentsService, SettingsService
from src.services.models.users import WalletTransactionService, UserService, MoneyTransferService, \
    NotificationSettingsService
from src.services.models.users.permission_service import PermissionService


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
