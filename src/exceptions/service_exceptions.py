class CategoryNotFound(Exception):
    pass

class NotEnoughAccounts(Exception):
    """Если пользователь пытается приобрести аккаунтов больше чем имеется"""
    pass

class NotEnoughMoney(Exception):
    """Если у пользователя недостаточно средств"""
    def __init__(self, message, need_money: int):
        self.message = message
        self.need_money = need_money
        super().__init__(self.message)

class InvalidPromoCode(Exception):
    pass

class PromoCodeAlreadyActivated(Exception):
    pass

class UserNotFound(Exception):
    pass

class TranslationAlreadyExists(Exception):
    pass

class ServiceTypeBusy(Exception):
    pass

class ServiceContainsCategories(Exception):
    """Сервис хранит категории"""
    pass

class CategoryStoresSubcategories(Exception):
    """Категория хранит подкатегории"""
    pass

class TheCategoryStorageAccount(Exception):
    """Категория хранит аккаунты"""
    pass

class IncorrectedNumberButton(Exception):
    """Некорректное число кнопок в одной строке. Ограничение: от 1 до 8 """
    pass

class IncorrectedAmountSale(Exception):
    """Некорректная сумма продажи"""
    pass

class IncorrectedCostPrice(Exception):
    """Некорректная себестоимость аккаунта"""
    pass

class AccountServiceNotFound(Exception):
    pass

class AccountCategoryNotFound(Exception):
    pass