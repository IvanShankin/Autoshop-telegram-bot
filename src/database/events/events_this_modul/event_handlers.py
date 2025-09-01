import orjson
from sqlalchemy import update

from src.database.core_models import Users, WalletTransaction, UserAuditLogs
from src.database.database import get_db
from src.database.events.events_this_modul.schemas import NewReplenishment
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.time_storage import TIME_USER


async def user_event_handler(event):
    """Обрабатывает event запуская определённую функцию"""
    if isinstance(event, NewReplenishment):
        await handler_new_replenishment(event)



async def handler_new_replenishment(new_replenishment: NewReplenishment):
    """Обрабатывает создание нового пополнения у пользователя"""
    async with get_db() as session_db:

        result_db = await session_db.execute(
            update(Users)
            .where(Users.user_id == new_replenishment.user_id)
            .values(
                balance=Users.balance + new_replenishment.amount,
                total_sum_replenishment=Users.total_sum_replenishment + new_replenishment.amount
            )
            .returning(
                Users.user_id,
                Users.username,
                Users.language,
                Users.unique_referral_code,
                Users.balance,
                Users.total_sum_replenishment,
                Users.total_sum_from_referrals,
                Users.created_at
            )
        )

        row_with_user = result_db.one()
        # создаём объект ORM через merge, чтобы он был привязан к сессии
        updated_user = await session_db.merge(
            Users(**dict(row_with_user._mapping))
        )

        # обновление связанных таблиц
        new_wallet_transaction = WalletTransaction(
            user_id = new_replenishment.user_id,
            type = 'replenish',
            amount = new_replenishment.amount,
            balance_before = updated_user.balance - new_replenishment.amount,
            balance_after = updated_user.balance ,
        )
        new_log = UserAuditLogs(
            user_id = new_replenishment.user_id,
            action_type = 'replenish',
            details = {'amount': new_replenishment.amount,'new_balance': updated_user.balance }
        )

        session_db.add(new_wallet_transaction)
        session_db.add(new_log)
        await session_db.commit()

    # кэшируем в redis
    async with get_redis() as session_redis:
        await session_redis.setex(f'user:{updated_user.user_id}', TIME_USER, orjson.dumps(updated_user.to_dict()))
