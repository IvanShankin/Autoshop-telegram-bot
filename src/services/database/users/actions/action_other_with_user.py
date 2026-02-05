from datetime import datetime, timezone
from typing import List, Optional, Any, Dict

import orjson
from asyncpg.pgproto.pgproto import timedelta
from sqlalchemy import select, update, delete, func

from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.broker.producer import publish_event
from src.config import get_config
from src.exceptions import UserNotFound, NotEnoughMoney
from src.services.redis.filling import filling_user
from src.services.database.admins.models import AdminActions
from src.services.database.referrals.utils import create_unique_referral_code
from src.services.database.users.actions.action_user import get_user
from src.services.database.users.models import Users, NotificationSettings, BannedAccounts, UserAuditLogs, \
    WalletTransaction, \
    TransferMoneys, Replenishments
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis
from src.services.redis.time_storage import TIME_USER, TIME_SUBSCRIPTION_PROMPT
from src.bot_actions.messages import send_log
from src.utils.core_logger import get_logger


async def add_new_user(user_id: int, username: str, language: str = 'ru') -> Users:
    """Создаст нового пользователя и прикрепит к нему настройки уведомлений"""
    user = Users(
        user_id = user_id,
        username = username,
        language = language,
        unique_referral_code = await create_unique_referral_code(),
        balance = 0,
        total_sum_replenishment = 0,
        total_profit_from_referrals = 0,
        created_at = datetime.now(timezone.utc)
    )
    new_notification = NotificationSettings(
        user_id = user_id
    )
    new_log = UserAuditLogs(
        user_id=user_id,
        action_type="new_user",
        message="Пользователь зарегистрировался в боте"
    )
    async with get_db() as session_db:
        session_db.add(user)
        await session_db.commit()
        session_db.add(new_notification)
        session_db.add(new_log)
        await session_db.commit()
        await session_db.refresh(user)

    async with get_redis() as session_redis:
        await session_redis.setex(f'user:{user_id}', TIME_USER, orjson.dumps(user.to_dict()))
        await session_redis.setex(f'subscription_prompt:{user_id}', TIME_SUBSCRIPTION_PROMPT, '_')

    event = EventSentLog(
        text=f"#Новый_пользователь \n\nID: {user_id}\nusername: {username}",
        log_lvl=LogLevel.INFO
    )
    await publish_event(event.model_dump(), "message.send_log")

    return user

async def get_notification(user_id) -> NotificationSettings | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
        return result_db.scalar_one_or_none()

async def update_notification(
        user_id: int,
        referral_invitation: bool,
        referral_replenishment: bool
) -> NotificationSettings | None:
    async with (get_db() as session_db):
        result_db = await session_db.execute(
            update(NotificationSettings)
            .where(NotificationSettings.user_id == user_id)
            .values(
                referral_invitation = referral_invitation,
                referral_replenishment = referral_replenishment
            )
            .returning(NotificationSettings)
        )
        await session_db.commit()
        return result_db.scalar_one_or_none()

async def get_banned_account(user_id: int) -> str | None:
    """
    Проверит только в redis (в нём сохраняется навсегда)
    :return: Причина бана, если забанен иначе None
    """
    async with get_redis() as session_redis:
        result_redis = await session_redis.get(f"banned_account:{user_id}")

    return None if result_redis is None else result_redis


async def add_banned_account(admin_id: int, user_id: int, reason: str):
    """
    Создаст новый забаненный аккаунт, залогирует и отошлёт в канал данное действие админа
    :param admin_id: id админа который это сделал
    :param user_id: id пользователя
    :param reason: Причина
    :exception UserNotFound: Если пользователь не найден
    """
    if not await get_user(user_id):
        raise UserNotFound(f"Пользователь с id = {user_id} не найден")

    new_ban = BannedAccounts(
        user_id = user_id,
        reason = reason
    )
    new_admin_log = AdminActions(
        user_id=admin_id,
        action_type = "added ban account",
        message = "Добавил аккаунт в забаненные",
        details = {"user_id": user_id }
    )
    async with get_db() as session_db:
        session_db.add(new_ban)
        session_db.add(new_admin_log)
        await session_db.commit()

    async with get_redis() as session_redis:
        await session_redis.set(f"banned_account:{user_id}", reason)

    event = EventSentLog(
        text=(
            f"🛠️\n"
            f"#Аккаунт_забанен \n\n"
            f"Админ c ID = '{admin_id}' \n"
            f"Добавил нового пользователя в забаненные аккаунты \n\n"
            f"ID Пользователя: '{user_id}'\n"
            f"Причина: '{reason}'"
        ),
        log_lvl=LogLevel.INFO
    )
    await publish_event(event.model_dump(), "message.send_log")


async def delete_banned_account(admin_id: int, user_id: int):
    if not await get_banned_account(user_id):
        raise UserNotFound(f"Пользователь с id = {user_id} не забанен")

    new_admin_log = AdminActions(
        user_id=admin_id,
        action_type="deleted ban account",
        message="Удалил аккаунт из забаненных",
        details={"user_id": user_id}
    )

    async with get_db() as session_db:
        await session_db.execute(delete(BannedAccounts).where(BannedAccounts.user_id == user_id))
        session_db.add(new_admin_log)
        await session_db.commit()

    async with get_redis() as session_redis:
        await session_redis.delete(f"banned_account:{user_id}")

    event = EventSentLog(
        text=(
            f"🛠️\n"
            f"#Аккаунт_разбанен \n\n"
            f"Админ c ID = '{admin_id}' разбанил пользователя \n"
            f"ID разбаненного аккаунта: '{user_id}'"
        ),
        log_lvl=LogLevel.INFO
    )
    await publish_event(event.model_dump(), "message.send_log")


async def get_wallet_transaction(wallet_transaction_id: int) -> WalletTransaction:
    async with get_db() as session_db:
        result = await session_db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.wallet_transaction_id == wallet_transaction_id)
        )
        return result.scalar_one_or_none()


async def get_wallet_transaction_page(user_id: int, page: int = None, page_size: int = None) -> List[WalletTransaction]:
    """Если не указывать page, то вернётся весь список. Отсортирован по дате (desc)"""
    if not page_size:
        page_size = get_config().different.page_size

    async with get_db() as session_db:
        query = select(
            WalletTransaction
        ).where(WalletTransaction.user_id == user_id).order_by(WalletTransaction.created_at.desc())

        if page:
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)

        result_db = await session_db.execute(query)
        return result_db.scalars().all()

async def get_count_wallet_transaction(user_id: int) -> int:
    async with get_db() as session_db:
        result = await session_db.execute(
            select(func.count()).where(WalletTransaction.user_id == user_id)
        )
        return result.scalar()


async def money_transfer(sender_id: int, recipient_id: int, amount: int):
    """
    :param sender_id: отправитель
    :param recipient_id: получатель
    :param amount: сумма
    :except UserNotFound: Если получатель не найден
    :except NotEnoughMoney: Если недостаточно денег
    """
    sender = await get_user(sender_id)
    recipient = await get_user(recipient_id)

    if not recipient or not sender:
        raise UserNotFound()

    if sender.balance < amount:
        raise NotEnoughMoney('Not enough money to transfer', amount - sender.balance)

    try:
        async with get_db() as session_db:
            async with session_db.begin():  # транзакция commit произойдет автоматически при выходе из блока
                result_sender = await session_db.execute(
                    select(Users).where(Users.user_id == sender_id).with_for_update()
                )
                result_recipient = await session_db.execute(
                    select(Users).where(Users.user_id == recipient_id).with_for_update()
                )
                sender = result_sender.scalar_one_or_none()
                recipient = result_recipient.scalar_one_or_none()
                sender.balance -= amount
                recipient.balance += amount

                transfer = TransferMoneys(
                    user_from_id = sender_id,
                    user_where_id = recipient_id,
                    amount = amount
                )
                wallet_trans_sender = WalletTransaction(
                    user_id = sender_id,
                    type = 'transfer',
                    amount = amount * -1,
                    balance_before = sender.balance - amount,
                    balance_after = sender.balance
                )
                wallet_trans_recipient = WalletTransaction(
                    user_id = recipient_id,
                    type = 'transfer',
                    amount = amount,
                    balance_before = recipient.balance - amount, # т.к. ранее обновили баланс
                    balance_after = recipient.balance
                )

                session_db.add(transfer)
                session_db.add(wallet_trans_sender)
                session_db.add(wallet_trans_recipient)

            await session_db.refresh(transfer)

            await session_db.refresh(sender)
            await session_db.refresh(recipient)

            await filling_user(sender)
            await filling_user(recipient)

            log_sender = UserAuditLogs(
                user_id = sender_id,
                action_type = "transfer",
                message='Пользователь отправил средства',
                details={
                    'transfer_money_id': transfer.transfer_money_id,
                    "recipient_id": recipient_id,
                    'amount': amount
                }
            )
            log_recipient = UserAuditLogs(
                user_id=recipient_id,
                action_type="transfer",
                message='Пользователь получил средства',
                details={
                    'transfer_money_id': transfer.transfer_money_id,
                    "sender_id": sender_id,
                    'amount': amount
                }
            )
            session_db.add(log_sender)
            session_db.add(log_recipient)
            await session_db.commit()
    except Exception as e:
        event = EventSentLog(
            text=f"#Ошибка_при_переводе_денег \n\nID пользователя: {sender_id} \nОшибка: {e}",
            log_lvl=LogLevel.ERROR
        )
        await publish_event(event.model_dump(), "message.send_log")
        logger = get_logger(__name__)
        logger.exception(f"ошибка: {e}")


async def get_replenishment(replenishment_id: int) -> Replenishments | None:
    async with get_db() as session_db:
        result = await session_db.execute(
            select(Replenishments)
            .where(Replenishments.replenishment_id == replenishment_id)
        )
        return result.scalar_one_or_none()


async def create_replenishment(
        user_id: int,
        type_payment_id: int,
        origin_amount_rub: int,
        amount_rub: int,
) -> Replenishments:
    """
    Создает Replenishments в БД. Статус выставляется автоматически "pending"

    Args:
        user_id: ID пользователя (обязательный)
        type_payment_id: ID типа платежа (обязательный)
        origin_amount_rub: Сумма в рублях без учёта комиссии (обязательный)
        amount_rub: Сумма в рублях с учётом комиссии (обязательный)
    """
    async with get_db() as session_db:
        new_replenishment = Replenishments(
            user_id = user_id,
            type_payment_id=type_payment_id,
            origin_amount = origin_amount_rub,
            amount = amount_rub,
        )
        session_db.add(new_replenishment)
        await session_db.commit()
        await session_db.refresh(new_replenishment)
    return new_replenishment


async def update_replenishment(
    replenishment_id: int,
    status: str,
    payment_system_id: Optional[str] = None,
    invoice_url: Optional[str] = None,
    expire_at: datetime = None,
    payment_data: Optional[Dict[str, Any]] = None,
) -> Replenishments:
    """
    Args:
        replenishment_id: ID пополнения
        status: Статус
        payment_system_id: ID транзакции в системе платежа
        invoice_url: URL для оплаты
        expire_at: Срок действия платежа.
        payment_data: Дополнительные данные платежа в формате JSON
    """
    async with get_db() as session_db:
        result = await session_db.execute(
            update(Replenishments)
            .where(Replenishments.replenishment_id == replenishment_id)
            .values(
                payment_system_id=payment_system_id,
                status=status,
                invoice_url=invoice_url,
                expire_at=datetime.now(timezone.utc) + timedelta(seconds=get_config().different.payment_lifetime_seconds) if expire_at is None else None,
                payment_data=payment_data
            )
            .returning(Replenishments)
        )
        replenishment = result.scalar_one()
        await session_db.commit()
    return replenishment


async def get_all_user_audit_logs(user_id: int) -> List[UserAuditLogs]:
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(UserAuditLogs)
            .where(UserAuditLogs.user_id == user_id)
            .order_by(UserAuditLogs.created_at.desc())
        )
        return result_db.scalars().all()


async def get_transfer_money(transfer_money_id: int) -> TransferMoneys:
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(TransferMoneys)
            .where(TransferMoneys.transfer_money_id == transfer_money_id)
        )
        return result_db.scalar_one_or_none()