from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, JSON, Enum, CheckConstraint, Index, \
    BigInteger, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from srс.database.base import Base


class Settings(Base):
    __tablename__ = "settings"

    settings_id = Column(Integer, primary_key=True, autoincrement=True)
    hash_token_accountant_bot = Column(Text, nullable=True)
    channel_for_logging_id = Column(String(200), nullable=True)   # ID канала для логирования
    channel_for_subscription_id = Column(String(200), nullable=True)   # ID канала для подписки пользователя

class Users(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index('ix_users_username', 'username'),
        Index('ix_users_referral_code', 'unique_referral_code'),
        Index('ix_users_created', 'created_at'),
        Index('ix_users_balance_created', 'balance', 'created_at')
    )

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    username = Column(String(150), nullable=False)
    language = Column(Enum("rus", "eng", name="user_language"), nullable=False, server_default="rus")  # язык пользователя
    unique_referral_code = Column(String(150), unique=True, nullable=False)
    balance = Column(Integer, default=0, nullable=False) # указанно в рублях
    total_sum_replenishment = Column(Integer, nullable=False, default=0)
    total_sum_from_referrals = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # связи
    admin = relationship("Admins", back_populates="user")
    message_for_sending = relationship("MessageForSending", back_populates="user")
    sent_mas_messages = relationship("SentMasMessages", back_populates="user")
    notification_settings = relationship("NotificationSettings", back_populates="user")

    # ЯВЛЯЕТСЯ владельцем (кто пригласил) для своих рефералов
    owned_referrals  = relationship("Referrals", foreign_keys="Referrals.owner_user_id", back_populates="owner")
    # ЯВЛЯЕТСЯ рефералом (кого пригласили) у своего владельца
    referred_by_link = relationship("Referrals", foreign_keys="Referrals.referral_id", back_populates="referral", uselist=False)

    # Доход, который ЭТОТ пользователь (владелец) получил от своих рефералов
    income_as_owner = relationship("IncomeFromReferrals", foreign_keys="IncomeFromReferrals.owner_user_id", back_populates="owner")
    # Доход, который кто-то получил с ЭТОГО пользователя (реферала)
    income_as_referral = relationship("IncomeFromReferrals", foreign_keys="IncomeFromReferrals.referral_id", back_populates="referral")

    replenishments = relationship("Replenishment", back_populates="user")
    banned_accounts = relationship("BannedAccounts", foreign_keys="BannedAccounts.user_id", back_populates="user")
    promo_code_activated_account = relationship("ActivatedPromoCode", foreign_keys="ActivatedPromoCode.user_id", back_populates="user")
    purchases = relationship("PurchasesAccounts", back_populates="user")
    sold_account = relationship("SoldAccount", back_populates="user")
    vouchers = relationship("Vouchers", back_populates="user")
    voucher_activations = relationship("VoucherActivations", back_populates="user")

    transfer_from = relationship("TransferMoney", foreign_keys="TransferMoney.user_from_id", back_populates="user_from")
    transfer_where = relationship("TransferMoney", foreign_keys="TransferMoney.user_where_id", back_populates="user_where")

    audit_logs = relationship("UserAuditLog",back_populates="user")
    admin_actions = relationship("AdminActions",back_populates="user")
    wallet_transactions = relationship("WalletTransaction",back_populates="user")

class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    notification_setting_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, unique=True)

    # Уведомления о рефералах
    referral_invitation = Column(Boolean, server_default=text('true'))  # Приглашение реферала
    referral_level_up = Column(Boolean, server_default=text('true'))  # Повышение уровня реферала
    referral_replenishment = Column(Boolean, server_default=text('true'))  # Пополнение реферала

    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("Users", back_populates="notification_settings")

# кэшируем в redis бессрочно.
class BannedAccounts(Base):
    __tablename__ = "banned_accounts"

    banned_account_id = Column(Integer, primary_key=True, autoincrement=True,)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    reason = Column(Text, nullable=False) # причина

    user = relationship("Users", back_populates="banned_accounts")

# Эту таблицу в боте нельзя менять. Тут по умолчанию должно быть поле с "телеграм" и "другой".
# В дальнейших обновлениях будут расширятся сервисы с которыми работаем
class TypeAccountServices(Base):
    __tablename__ = "type_account_services"

    type_account_service_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)

    account_service = relationship("AccountService", back_populates="type_account_service")
    product_accounts = relationship("Accounts", back_populates="type_account_service")
    sold_accounts = relationship("SoldAccount", back_populates="type_account_service")

class TypePayments(Base):
    __tablename__ = "type_payments"

    type_payment_id = Column(Integer, primary_key=True, autoincrement=True)
    # у админа будет собственное название (только для него в панели администратора)
    name_for_user = Column(String(300), nullable=False)  # Название метода (CryptoBot, ЮMoney и т.д.)
    name_for_admin = Column(String(300), nullable=False)
    is_active = Column(Boolean, server_default=text('true'))  # Активен ли метод
    commission = Column(Integer, default=0)  # Комиссия в процентах
    extra_data = Column(JSON, nullable=True)  # Дополнительные параметры метода

    replenishments = relationship("Replenishment", back_populates="type_payment")

class Replenishments(Base):
    __tablename__ = "replenishments"

    replenishment_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    type_payment_id = Column(Integer, ForeignKey("type_payment.type_payment_id"), nullable=False)
    origin_amount = Column(Integer, nullable=False)  # Сумма в рублях (без учёта комиссии)
    amount = Column(Integer, nullable=False)  # Сумма в рублях (с учётом комиссии)
    status = Column(Enum('pending', 'completed', 'cancelled', 'failed', name='replenishment_status'), server_default='pending')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Универсальные поля для разных платежных систем
    payment_system_id = Column(String(500))  # ID транзакции в системе платежа
    invoice_url = Column(Text, nullable=True)  # URL для оплаты
    expire_at = Column(DateTime(timezone=True))  # Срок действия платежа
    payment_data = Column(JSON, nullable=True)  # Дополнительные данные платежа

    user = relationship("Users", back_populates="replenishments")
    type_payment = relationship("TypePayment", back_populates="replenishments")

class TransferMoneys(Base):
    __tablename__ = "transfer_moneys"

    transfer_money_id = Column(Integer, primary_key=True, autoincrement=True)
    user_from_id = Column(Integer, ForeignKey("users.user_id"), nullable=False) # от кого
    user_where_id = Column(Integer, ForeignKey("users.user_id"), nullable=False) # кому
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user_from = relationship("Users", foreign_keys=[user_from_id], back_populates="transfer_from")
    user_where = relationship("Users", foreign_keys=[user_where_id], back_populates="transfer_where")

class UserAuditLogs(Base):
    __tablename__ = "user_audit_logs"

    user_audit_log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)  # Кто совершил действие
    action_type = Column(String(100), nullable=False)  # Тип действия (может быть любое)
    details = Column(JSON, nullable=True)  # Гибкое поле для любых деталей
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="audit_logs")

class BackupLogs(Base):
    __tablename__ = "backup_logs"

    backup_log_id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    size_in_kilobytes = Column(Integer, nullable=False)

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    wallet_transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    type = Column(Enum('replenish','purchase','refund','transfer','promo', name='wallet_tx_type'), nullable=False)
    amount = Column(Integer, nullable=False)
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="wallet_transactions")