from src.services.database.events.core_event import subscribe, run_dispatcher
from src.services.discounts.events import promo_code_event_handler, voucher_event_handler
from src.services.replenishments_event.event_handlers_replenishments import user_event_handler
from src.services.referrals.events import referral_event_handler

async def run_triggers_processing():
    """Запускает все обработчики событий в БД"""
    # регистрируем обработчики
    subscribe(user_event_handler, priority=0)
    subscribe(referral_event_handler, priority=1)
    subscribe(promo_code_event_handler, priority=0)
    subscribe(voucher_event_handler, priority=0)

    # запускаем run_dispatcher и ждем его (он завершится только по sentinel)
    await run_dispatcher()
