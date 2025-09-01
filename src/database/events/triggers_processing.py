from src.database.events.core_event import subscribe, run_dispatcher
from src.database.events.events_this_modul.event_handlers import user_event_handler
from src.modules.referrals.event_handlers_referral import referral_event_handler

async def run_triggers_processing():
    """Запускает все обработчики событий в БД"""
    # регистрируем обработчики
    subscribe(user_event_handler)
    subscribe(referral_event_handler)

    # запускаем run_dispatcher и ждем его (он завершится только по sentinel)
    await run_dispatcher()
