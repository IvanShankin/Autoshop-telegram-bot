from aiogram.fsm.state import StatesGroup, State

class BuyAccount(StatesGroup):
    promo_code = State()
    quantity_accounts = State()
