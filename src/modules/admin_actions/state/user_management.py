from aiogram.fsm.state import State, StatesGroup


class GetUserIdOrUsername(StatesGroup):
    get_id_or_username = State()

class SetNewBalance(StatesGroup):
    new_balance = State()

class IssueBan(StatesGroup):
    issue_ban = State()