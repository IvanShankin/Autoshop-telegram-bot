from src.database.events.events_this_modul.schemas import NewReplenishment

async def referral_event_handler(event):
    if isinstance(event, NewReplenishment):
        await handler_new_replenishment(event)

async def handler_new_replenishment(new_replenishment: NewReplenishment):
    pass
    # тут своя логика для рефералов
