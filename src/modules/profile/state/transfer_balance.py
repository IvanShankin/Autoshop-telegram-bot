from aiogram.fsm.state import StatesGroup, State


class TransferMoney(StatesGroup):
    amount = State()
    recipient_id = State()

class CreateVoucher(StatesGroup):
    amount = State()
    number_of_activations = State()