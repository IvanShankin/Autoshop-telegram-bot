from aiogram.fsm.state import StatesGroup, State


class UpdateAdminSettings(StatesGroup):
    support_username = State()
    channel_for_logging_id = State()
    channel_for_subscription_id = State()
    channel_for_subscription_url = State()
    channel_name = State()
    shop_name = State()
    faq_url = State()


class AddAdmin(StatesGroup):
    user_id = State()


class DeleteAdmin(StatesGroup):
    user_id = State()