from datetime import datetime, timezone
from typing import List

import orjson
from sqlalchemy import select, update, delete, func

from src.config import PAGE_SIZE
from src.exceptions.service_exceptions import UserNotFound, NotEnoughMoney
from src.services.redis.filling_redis import filling_user
from src.services.database.admins.models import AdminActions
from src.services.database.referrals.utils import create_unique_referral_code
from src.services.database.users.actions.action_user import get_user
from src.services.database.users.models import Users, NotificationSettings, BannedAccounts, UserAuditLogs, WalletTransaction, \
    TransferMoneys
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis
from src.services.redis.time_storage import TIME_USER
from src.bot_actions.actions import send_log
from src.utils.core_logger import logger


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
        action_type = "new_user"
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

    await send_log(f"#Новый_пользователь \n\nID: {user_id}\nusername: {username}")

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
    Проверит только в redis
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
        details = {'message': "Добавил аккаунт в забаненные", "user_id": user_id }
    )
    async with get_db() as session_db:
        session_db.add(new_ban)
        session_db.add(new_admin_log)
        await session_db.commit()

    async with get_redis() as session_redis:
        await session_redis.set(f"banned_account:{user_id}", reason)

    await send_log(
        f"#Аккаунт_забанен \n\n"
        f"Админ c ID = '{admin_id}' \n"
        f"Добавил нового пользователя в забаненные аккаунты \n\n"
        f"ID Пользователя: '{user_id}'\n"
        f"Причина: '{reason}'"
    )

async def delete_banned_account(admin_id: int, user_id: int):
    if not await get_banned_account(user_id):
        raise UserNotFound(f"Пользователь с id = {user_id} не забанен")

    new_admin_log = AdminActions(
        user_id=admin_id,
        action_type="deleted ban account",
        details={'message': "Удалил аккаунт из забаненных", "user_id": user_id}
    )

    async with get_db() as session_db:
        await session_db.execute(delete(BannedAccounts).where(BannedAccounts.user_id == user_id))
        session_db.add(new_admin_log)
        await session_db.commit()

    async with get_redis() as session_redis:
        await session_redis.delete(f"banned_account:{user_id}")

    await send_log(
        f"#Аккаунт_разбанен \n\n"
        f"Админ c ID = '{admin_id}' разбанил пользователя \n"
        f"ID разбаненного аккаунта: '{user_id}'"
    )


async def get_wallet_transaction(wallet_transaction_id: int) -> WalletTransaction:
    async with get_db() as session_db:
        result = await session_db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.wallet_transaction_id == wallet_transaction_id)
        )
        return result.scalar_one_or_none()


async def get_wallet_transaction_page(user_id: int, page: int = None, page_size: int = PAGE_SIZE) -> List[WalletTransaction]:
    """Если не указывать page, то вернётся весь список. Отсортирован по дате (desc)"""
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
                    amount = amount,
                    balance_before = sender.balance - amount,
                    balance_after = sender.balance
                )
                wallet_trans_recipient = WalletTransaction(
                    user_id = recipient_id,
                    type = 'transfer',
                    amount = amount,
                    balance_before = recipient.balance - amount,
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
                details = {
                    'message': 'Пользователь отправил средства',
                    'transfer_money_id': transfer.transfer_money_id,
                    "recipient_id": recipient_id,
                    'amount': amount
                }
            )
            log_recipient = UserAuditLogs(
                user_id=recipient_id,
                action_type="transfer",
                details={
                    'message': 'Пользователь получил средства',
                    'transfer_money_id': transfer.transfer_money_id,
                    "sender_id": sender_id,
                    'amount': amount
                }
            )
            session_db.add(log_sender)
            session_db.add(log_recipient)
            await session_db.commit()
    except Exception as e:
        await send_log(f"#Ошибка_при_переводе_денег \n\nID пользователя: {sender_id} \nОшибка: {e}")
        logger.exception(f"ошибка: {e}")

