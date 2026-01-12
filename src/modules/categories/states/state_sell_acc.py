from aiogram.fsm.state import StatesGroup, State

class BuyProduct(StatesGroup):
    promo_code = State()
    quantity_products = State()
