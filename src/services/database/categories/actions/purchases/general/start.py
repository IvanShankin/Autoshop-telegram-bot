from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import CategoryNotFound, NotEnoughMoney
from src.services.database.categories.actions.actions_get import get_categories_by_category_id
from src.services.database.categories.models import CategoryTranslation
from src.services.database.categories.models import PurchaseRequests
from src.services.database.categories.models import ResultCheckCategory
from src.services.database.core.database import get_db
from src.services.database.discounts.utils.calculation import discount_calculation
from src.services.database.users.actions import get_user
from src.services.database.users.models import Users
from src.services.database.users.models.models_users import BalanceHolder


async def check_category_and_money(
    user_id: int,
    category_id: int,
    quantity_products: int,
    promo_code_id: Optional[int]
) -> ResultCheckCategory:
    # получаем категорию
    category = await get_categories_by_category_id(category_id)

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(CategoryTranslation)
            .where(CategoryTranslation.category_id == category_id)
        )
        translations_category: list[CategoryTranslation] = result_db.scalars().all()

    if not category or not translations_category:
        raise CategoryNotFound("Данной категории больше не существует")

    original_price_per = category.price
    original_total = original_price_per * quantity_products  # оригинальная сумма которую должен заплатить пользователь

    # рассчитываем скидку
    if promo_code_id:
        discount_amount, _ = await discount_calculation(original_total, promo_code_id=promo_code_id)
    else:
        discount_amount = 0
    final_total = max(0, original_total - discount_amount)  # конечная сумма которую должен заплатить пользователь

    # проверяем баланс пользователя
    user = await get_user(user_id)
    user_balance_before = user.balance
    if user.balance < final_total:
        raise NotEnoughMoney("Недостаточно средств для покупки товара", final_total - user.balance)

    return ResultCheckCategory(
        category=category,
        category_translations=translations_category,
        final_total=final_total,
        user_balance_before=user_balance_before
    )


async def create_new_purchase_request(
    session_db: AsyncSession,
    user_id: int,
    promo_code_id: int,
    quantity_products: int,
    final_total: int
) -> PurchaseRequests:
    """
    :param session_db: В транзакции
    """
    new_purchase_requests = PurchaseRequests(
        user_id=user_id,
        promo_code_id=promo_code_id,
        quantity=quantity_products,
        total_amount=final_total,
        status='processing'
    )
    session_db.add(new_purchase_requests)
    await session_db.flush()
    return new_purchase_requests


async def write_off_of_funds(
    session_db: AsyncSession,
    user_id: int,
    purchase_request_id: int,
    final_total: int,
) -> Users | None:
    """
    :param session_db: В транзакции
    """
    new_balance_holder = BalanceHolder(
        purchase_request_id=purchase_request_id,
        user_id=user_id,
        amount=final_total
    )
    session_db.add(new_balance_holder)
    result_db = await session_db.execute(
        update(Users)
        .where(Users.user_id == user_id)
        .values(balance=Users.balance - final_total)
        .returning(Users)
    )
    return result_db.scalar()
