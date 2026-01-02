from src.exceptions import InvalidPromoCode
from src.services.database.discounts.actions import get_promo_code
from src.services.database.discounts.models import PromoCodes


async def discount_calculation(
        amount: int,
        code_promo_code: str = None,
        promo_code_id: int = None
) -> tuple[int, PromoCodes]:
    """
    Рассчитает скидку с промокодом
    :return: tuple[скидка (int), id промокода (int), найденный промокод (PromoCodes)]
    """
    promo_code = await get_promo_code(code_promo_code, promo_code_id)
    if not promo_code:
        raise InvalidPromoCode("Промокод невалидный")

    if promo_code.amount is not None:
        discount_amount = min(promo_code.amount, amount)
    elif promo_code.discount_percentage is not None:
        # явный int (рубли/копейки) — округляем вниз
        discount_amount = (amount * promo_code.discount_percentage) // 100
    else:
        discount_amount = 0

    discount_amount = max(0, discount_amount)

    return discount_amount, promo_code