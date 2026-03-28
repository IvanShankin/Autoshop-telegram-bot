from datetime import datetime

from pydantic import BaseModel

from src.database.models.categories import ProductType


class SettingsDTO(BaseModel):
    settings_id: int
    maintenance_mode: bool
    support_username: str               # хранит просто текст, без @
    channel_for_logging_id: int         # ID канала для логирования
    channel_for_subscription_id: int    # ID канала для подписки пользователя
    channel_for_subscription_url: str   # опционально
    channel_name: str
    shop_name: str
    FAQ: str                            # ссылка


class UsersDTO(BaseModel):
    user_id: int                 # одновременно telegram_id
    username: str | None
    language: str                # язык пользователя (ru/en)
    unique_referral_code: str    # уникальный реферальный код
    balance: int                 # баланс в рублях
    total_sum_replenishment: int # общая сумма пополнений
    total_profit_from_referrals: int  # общая прибыль от рефералов
    created_at: datetime
    last_used: datetime


class BannedAccountsDTO(BaseModel):
    banned_account_id: int
    user_id: int
    reason: str                  # причина блокировки
    created_at: datetime


class StickersDTO(BaseModel):
    key: str                     # ключ из message_event
    file_id: str | None          # file_id стикера
    show: bool                   # показывать или нет
    updated_at: datetime         # время последнего обновления


class UiImagesDTO(BaseModel):
    key: str                     # ключ для категории или message_event
    file_name: str               # имя файла
    file_id: str | None          # file_id изображения
    show: bool                   # показывать или нет
    updated_at: datetime         # время последнего обновления


class ReferralsDTO(BaseModel):
    referral_id: int             # ID пользователя, которого пригласили (реферала)
    owner_user_id: int           # ID пользователя, который пригласил (владельца)
    level: int                   # уровень реферальной сети
    created_at: datetime         # дата создания


class ReferralLevelsDTO(BaseModel):
    referral_level_id: int
    level: int                   # уровень реферальной системы
    amount_of_achievement: int   # сумма, с которой достигается уровень
    percent: float               # процент начисления


class TypePaymentsDTO(BaseModel):
    type_payment_id: int
    name_for_user: str           # Название метода (CryptoBot, ЮMoney и т.д.)
    name_for_admin: str          # Название для админа (из get_config().app.type_payments)
    is_active: bool              # Активен ли метод
    commission: float            # Комиссия в процентах
    index: int                   # порядковый индекс
    extra_data: dict | None      # Дополнительные параметры метода


class PromoCodesDTO(BaseModel):
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


class VouchersDTO(BaseModel):
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


class NotificationSettingsDTO(BaseModel):
    notification_setting_id: int
    user_id: int
    referral_invitation: bool
    referral_replenishment: bool
    updated_at: datetime | None


class ReplenishmentsDTO(BaseModel):
    replenishment_id: int
    user_id: int
    type_payment_id: int
    origin_amount: int
    amount: int
    status: str
    created_at: datetime
    updated_at: datetime | None
    payment_system_id: str | None
    invoice_url: str | None
    expire_at: datetime
    payment_data: dict | None


class TransferMoneysDTO(BaseModel):
    transfer_money_id: int
    user_from_id: int
    user_where_id: int
    amount: int
    created_at: datetime


class UserAuditLogsDTO(BaseModel):
    user_audit_log_id: int
    user_id: int
    action_type: str
    message: str
    details: dict | None
    created_at: datetime


class WalletTransactionDTO(BaseModel):
    wallet_transaction_id: int
    user_id: int
    type: str
    amount: int
    balance_before: int
    balance_after: int
    created_at: datetime


class FilesDTO(BaseModel):
    key: str
    file_path: str
    file_tg_id: str | None
    updated_at: datetime


class BackupLogsDTO(BaseModel):
    backup_log_id: int
    storage_file_name: str
    storage_encrypted_dek_name: str
    encrypted_dek_b64: str
    dek_nonce_b64: str
    size_bytes: int
    created_at: datetime


class ActivatedPromoCodesDTO(BaseModel):
    activated_promo_code_id: int
    promo_code_id: int
    user_id: int
    created_at: datetime


class VoucherActivationsDTO(BaseModel):
    voucher_activation_id: int
    voucher_id: int
    user_id: int | None
    created_at: datetime


class IncomeFromReferralsDTO(BaseModel):
    income_from_referral_id: int
    replenishment_id: int
    owner_user_id: int
    referral_id: int
    amount: int
    percentage_of_replenishment: int
    created_at: datetime


class PurchasesDTO(BaseModel):
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
