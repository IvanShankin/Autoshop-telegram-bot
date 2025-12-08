from aiogram.fsm.state import StatesGroup, State


class GetTypePaymentName(StatesGroup):
    new_name = State()


class GetTypePaymentCommission(StatesGroup):
    new_commission = State()