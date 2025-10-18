from aiogram.fsm.state import StatesGroup, State


class TransferMoney(StatesGroup):
    amount = State()
    recipient_id = State()