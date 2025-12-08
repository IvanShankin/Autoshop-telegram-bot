from aiogram.fsm.state import StatesGroup, State


class CreateAdminVoucher(StatesGroup):
    number_of_activations = State()
    expire_at = State()
    amount = State()