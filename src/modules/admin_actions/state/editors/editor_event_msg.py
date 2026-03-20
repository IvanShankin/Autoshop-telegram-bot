from aiogram.fsm.state import StatesGroup, State


class UpdateEventMsg(StatesGroup):
    get_new_image = State()
    get_new_sticker = State()
