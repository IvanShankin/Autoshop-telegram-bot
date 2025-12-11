from aiogram.fsm.state import StatesGroup, State


class GetImageMassMailing(StatesGroup):
    get_new_image = State()


class GetTextMassMailing(StatesGroup):
    get_new_text = State()


class GetBtnUrlMassMailing(StatesGroup):
    get_new_btn_url = State()