from src.services.database.events.core_event import subscribe, run_dispatcher
from src.services.discounts.events.event_handlers_promo_code import discounts_event_handler
from src.services.replenishments_event.event_handlers_replenishments import user_event_handler
from src.services.referrals.events import referral_event_handler

async def run_triggers_processing():
    """Запускает все обработчики событий в БД"""
    # регистрируем обработчики
    subscribe(user_event_handler, priority=0)
    subscribe(referral_event_handler, priority=1)
    subscribe(discounts_event_handler, priority=0)

    # запускаем run_dispatcher и ждем его (он завершится только по sentinel)
    await run_dispatcher()
