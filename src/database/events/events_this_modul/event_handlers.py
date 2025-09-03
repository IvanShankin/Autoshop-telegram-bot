import orjson
from sqlalchemy import update, select
from sqlalchemy.orm import object_session

from src.database.action_core_models import update_user, get_user
from src.database.core_models import Users, WalletTransaction, UserAuditLogs
from src.database.database import get_db
from src.database.events.core_event import push_deferred_event
from src.database.events.events_this_modul.schemas import NewReplenishment
from src.modules.referrals.database.events.schemas import NewIncomeFromRef
from src.modules.referrals.database.models import Referrals
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.time_storage import TIME_USER


async def user_event_handler(event):
    """Обрабатывает event запуская определённую функцию"""
    if isinstance(event, NewReplenishment):
        await handler_new_replenishment(event)



async def handler_new_replenishment(new_replenishment: NewReplenishment):
    """Обрабатывает создание нового пополнения у пользователя"""
    user = await get_user(new_replenishment.user_id)
    user.balance = user.balance + new_replenishment.amount
    user.total_sum_replenishment = user.total_sum_replenishment + new_replenishment.amount
    updated_user = await update_user(user)

    async with get_db() as session_db:
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

        result_db = await session_db.execute(select(Referrals).where(Referrals.referral_id == updated_user.user_id))
        referral = result_db.scalar_one_or_none()

        # если пользователь чей-то реферал, то запустим событие NewReplenishment
        if referral:
            session = object_session(NewReplenishment)  # Определяет объект сессии которая в данный момент управляет NewReplenishment
            if session:
                # откладываем событие
                push_deferred_event(
                    session,
                    NewIncomeFromRef(
                        referral_id=updated_user.user_id,
                        replenishment_id=new_replenishment.replenishment_id,
                        owner_id=referral.owner_user_id,
                        amount=new_replenishment.amount,
                        total_sum_replenishment=updated_user.total_sum_replenishment
                    )
                )
