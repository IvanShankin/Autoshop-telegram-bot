from aiogram.fsm.state import StatesGroup, State


class GetServiceName(StatesGroup):
    service_name = State()

class RenameService(StatesGroup):
    service_name = State()