from sqlalchemy import event
from sqlalchemy.orm import object_session
from src.database.core_models import Replenishments
from src.database.events.core_event import push_deferred_event
from src.database.events.events_this_modul.schemas import NewReplenishment



@event.listens_for(Replenishments, "after_update")
def event_update_replenishments(mapper, connection, target: Replenishments):
    """Создаёт event при изменении Replenishments"""
    if target.status != "completed":
        return

    session = object_session(target) # Определяет объект сессии которая в данный момент управляет target
    if session:
        # откладываем событие
        push_deferred_event(
            session,
            NewReplenishment(
                user_id=target.user_id,
                amount=target.amount,
                create_at=target.created_at,
            ),
        )
