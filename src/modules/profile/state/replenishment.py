from aiogram.fsm.state import StatesGroup, State

class GetAmount(StatesGroup):
    amount = State()

