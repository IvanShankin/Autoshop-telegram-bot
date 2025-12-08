from aiogram.fsm.state import StatesGroup, State


class CreatePromoCode(StatesGroup):
    get_amount = State()
    get_discount_percentage = State()
    get_number_of_activations = State()
    get_expire_at = State()
    get_min_order_amount = State()
    get_activation_code = State()
