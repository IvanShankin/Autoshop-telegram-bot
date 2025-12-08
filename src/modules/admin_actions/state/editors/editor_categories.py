from aiogram.fsm.state import StatesGroup, State


class GetServiceName(StatesGroup):
    service_name = State()


class RenameService(StatesGroup):
    service_name = State()


class GetDataForCategory(StatesGroup):
    category_name = State()
    category_description = State()


class UpdateNameForCategory(StatesGroup):
    name = State()


class UpdateDescriptionForCategory(StatesGroup):
    description = State()


class UpdateCategoryImage(StatesGroup):
    image = State()


class UpdateNumberInCategory(StatesGroup):
    price = State()
    cost_price = State()
    number_button = State()


class ImportTgAccounts(StatesGroup):
    archive = State()


class ImportOtherAccounts(StatesGroup):
    csv_file = State()