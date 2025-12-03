from aiogram.fsm.state import StatesGroup, State


class GetNewPersent(StatesGroup):
    get_new_persent = State()


class GetAchievementAmount(StatesGroup):
    get_new_achievement_amount = State()


class CreateRefLevel(StatesGroup):
    get_achievement_amount = State()
    get_persent = State()
