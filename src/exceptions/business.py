"""
Бизнес-исключения.
Исключения, связанные с нарушением бизнес-правил и логики приложения.
"""

from typing import Optional


class NotEnoughAccounts(Exception):
    """Если пользователь пытается приобрести аккаунтов больше чем имеется"""
    pass

class NotEnoughMoney(Exception):
    """Если у пользователя недостаточно средств"""
    def __init__(self, message, need_money: int):
        self.message = message
        self.need_money = need_money
        super().__init__(self.message)


class UnableRemoveMainAdmin(Exception):
    pass

class InvalidPromoCode(Exception):
    pass

class PromoCodeAlreadyActivated(Exception):
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

class TheCategoryNotStorageAccount(Exception):
    """Категория НЕ хранит аккаунты"""
    pass

class TheAccountServiceDoesNotMatch(Exception):
    """Не совпадает сервис аккаунтов"""
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

class SettingsNotFilled(Exception):
    """Настройки не заполнены"""
    pass

class InvalidFormatRows(Exception):
    """При распаковке csv файла, если у него не верный формат"""
    pass

class InvalidAmountOfAchievement(Exception):
    """
    Неверный amount_of_achievement при установках его в ReferralLevels.

    Он должен быть не меньше или равным прошлому уровню и не больше или равным следующему уровню
    """
    def __init__(
        self,
        amount_of_achievement_previous_lvl: Optional[int] = None,
        amount_of_achievement_next_lvl: Optional[int] = None
    ):
        self.amount_of_achievement_previous_lvl: int | None = amount_of_achievement_previous_lvl
        self.amount_of_achievement_next_lvl: int | None = amount_of_achievement_next_lvl

class InvalidSelectedLevel(Exception):
    """Первый уровень в реферальной системе нельзя удалять или менять сумму постижения его (всегда должна быть 0)"""
    pass

class TextTooLong(Exception):
    """При массовой рассылке, если текст для ОДНОГО сообщения слишком большой"""
    pass

class TextNotLinc(Exception):
    """Указанный текст не является ссылкой"""
    pass