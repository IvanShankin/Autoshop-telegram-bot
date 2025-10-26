from src.exceptions.service_exceptions import InvalidPromoCode
from src.services.database.discounts.actions import get_valid_promo_code


async def discount_calculation(amount: int, code_promo_code: str):
    """Рассчитает скидку с промокодом"""
    promo_code = await get_valid_promo_code(code_promo_code)
    if not promo_code:
        raise InvalidPromoCode("Промокод невалидный")

    if promo_code.amount is not None:
        discount_amount = min(promo_code.amount, amount)
    elif promo_code.discount_percentage is not None:
        # явный int (рубли/копейки) — округляем вниз
        discount_amount = (amount * promo_code.discount_percentage) // 100
    else:
        discount_amount = 0

    return discount_amount