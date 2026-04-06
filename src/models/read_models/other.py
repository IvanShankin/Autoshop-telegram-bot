from datetime import datetime

from src.database.models.categories import ProductType
from src.database.models.system.models import ReplenishmentService
from src.models.base import ORMDTO


class SettingsDTO(ORMDTO):
    settings_id: int
    maintenance_mode: bool
    support_username: str               # хранит просто текст, без @
    channel_for_logging_id: int         # ID канала для логирования
    channel_for_subscription_id: int    # ID канала для подписки пользователя
    channel_for_subscription_url: str   # опционально
    channel_name: str
    shop_name: str
    FAQ: str                            # ссылка


class UsersDTO(ORMDTO):
    user_id: int                 # одновременно telegram_id
    username: str | None
    language: str                # язык пользователя (ru/en)
    unique_referral_code: str    # уникальный реферальный код
    balance: int                 # баланс в рублях
    total_sum_replenishment: int # общая сумма пополнений
    total_profit_from_referrals: int  # общая прибыль от рефералов
    created_at: datetime
    last_used: datetime


class BannedAccountsDTO(ORMDTO):
    banned_account_id: int
    user_id: int
    reason: str                  # причина блокировки
    created_at: datetime


class StickersDTO(ORMDTO):
    key: str                     # ключ из message_event
    file_id: str | None          # file_id стикера
    show: bool                   # показывать или нет
    updated_at: datetime         # время последнего обновления


class UiImagesDTO(ORMDTO):
    key: str                     # ключ для категории или message_event
    file_name: str               # имя файла
    file_id: str | None          # file_id изображения
    show: bool                   # показывать или нет
    updated_at: datetime         # время последнего обновления


class ReferralsDTO(ORMDTO):
    referral_id: int             # ID пользователя, которого пригласили (реферала)
    owner_user_id: int           # ID пользователя, который пригласил (владельца)
    level: int                   # уровень реферальной сети
    created_at: datetime         # дата создания


class ReferralLevelsDTO(ORMDTO):
    referral_level_id: int
    level: int                   # уровень реферальной системы
    amount_of_achievement: int   # сумма, с которой достигается уровень
    percent: float               # процент начисления


class TypePaymentsDTO(ORMDTO):
    type_payment_id: int
    name_for_user: str           # Название метода (CryptoBot, ЮMoney и т.д.)
    service: ReplenishmentService
    is_active: bool              # Активен ли метод
    commission: float            # Комиссия в процентах
    index: int                   # порядковый индекс
    extra_data: dict | None      # Дополнительные параметры метода


class PromoCodesDTO(ORMDTO):
    promo_code_id: int
    activation_code: str         # промокод (не уникальный)
    min_order_amount: int        # минимальная сумма для применения
    activated_counter: int       # количество активаций
    amount: int | None           # сумма скидки
    discount_percentage: int | None  # процент скидки (0-100)
    number_of_activations: int | None  # разрешённое количество активаций
    start_at: datetime
    expire_at: datetime | None
    is_valid: bool


class ResultActivatePromoCodeDTO(ORMDTO):
    promo_code: PromoCodesDTO
    deactivate: bool        # True если деактивировали


class VouchersDTO(ORMDTO):
    voucher_id: int
    creator_id: int | None       # ForeignKey users.user_id
    is_created_admin: bool       # создан ли админом
    activation_code: str         # код активации (не уникальный)
    amount: int                  # сумма ваучера
    activated_counter: int       # количество активаций
    number_of_activations: int | None  # разрешённое количество активаций
    start_at: datetime
    expire_at: datetime | None
    is_valid: bool


class NotificationSettingsDTO(ORMDTO):
    notification_setting_id: int
    user_id: int
    referral_invitation: bool
    referral_replenishment: bool
    updated_at: datetime | None


class ReplenishmentsDTO(ORMDTO):
    replenishment_id: int
    user_id: int
    type_payment_id: int
    origin_amount: int
    amount: int
    status: str
    created_at: datetime
    updated_at: datetime | None
    service: ReplenishmentService
    payment_system_id: str | None
    invoice_url: str | None
    expire_at: datetime
    payment_data: dict | None


class TransferMoneysDTO(ORMDTO):
    transfer_money_id: int
    user_from_id: int
    user_where_id: int
    amount: int
    created_at: datetime


class UserAuditLogsDTO(ORMDTO):
    user_audit_log_id: int
    user_id: int
    action_type: str
    message: str
    details: dict | None
    created_at: datetime


class WalletTransactionDTO(ORMDTO):
    wallet_transaction_id: int
    user_id: int
    type: str
    amount: int
    balance_before: int
    balance_after: int
    created_at: datetime


class FilesDTO(ORMDTO):
    key: str
    file_path: str
    file_tg_id: str | None
    updated_at: datetime


class BackupLogsDTO(ORMDTO):
    backup_log_id: int
    storage_file_name: str
    storage_encrypted_dek_name: str
    encrypted_dek_b64: str
    dek_nonce_b64: str
    size_bytes: int
    created_at: datetime


class ActivatedPromoCodesDTO(ORMDTO):
    activated_promo_code_id: int
    promo_code_id: int
    user_id: int
    created_at: datetime


class VoucherActivationsDTO(ORMDTO):
    voucher_activation_id: int
    voucher_id: int
    user_id: int | None
    created_at: datetime


class IncomeFromReferralsDTO(ORMDTO):
    income_from_referral_id: int
    replenishment_id: int
    owner_user_id: int
    referral_id: int
    amount: int
    percentage_of_replenishment: int
    created_at: datetime


class PurchasesDTO(ORMDTO):
    purchase_id: int
    user_id: int
    product_type: ProductType | None
    account_storage_id: int | None
    universal_storage_id: int | None
    original_price: int
    purchase_price: int
    cost_price: int
    net_profit: int
    purchase_date: datetime
