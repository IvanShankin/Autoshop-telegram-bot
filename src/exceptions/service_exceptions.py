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
