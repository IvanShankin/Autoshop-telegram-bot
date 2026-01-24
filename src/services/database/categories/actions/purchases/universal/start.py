from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions.business import NotEnoughProducts
from src.exceptions.domain import UniversalProductNotFound
from src.services.database.categories.actions.products.universal.actions_get import get_product_universal_by_category_id
from src.services.database.categories.actions.purchases.general.start import write_off_of_funds, \
    create_new_purchase_request, check_category_and_money
from src.services.database.categories.models import ProductUniversal
from src.services.database.categories.models import ResultCheckCategory
from src.services.database.categories.models.product_universal import UniversalStorageStatus, PurchaseRequestUniversal, \
    UniversalStorage
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull
from src.services.database.categories.models.shemas.purshanse_schem import StartPurchaseUniversal, \
    StartPurchaseUniversalOne
from src.services.database.core.database import get_db
from src.services.redis.filling import filling_user, filling_all_keys_category
from src.services.redis.filling.filling_universal import filling_product_universal_by_category, \
    filling_universal_by_product_id


async def _set_reserved_universal(
    session_db: AsyncSession,
    category_id: int,
    quantity_products: int,
    purchase_request_id: int,
) -> List[ProductUniversal]:
    """
    :param session_db: В транзакции
    """
    q = (
        select(ProductUniversal)
        .options(selectinload(ProductUniversal.storage), selectinload(UniversalStorage.translations))
        .join(ProductUniversal.storage)
        .where(
            (ProductUniversal.category_id == category_id) &
            (UniversalStorage.status == UniversalStorageStatus.FOR_SALE)
        )
        .order_by(ProductUniversal.created_at.desc())
        .with_for_update()
        .limit(quantity_products)
    )
    result_db = await session_db.execute(q)
    product_universal: List[ProductUniversal] = result_db.scalars().all()
    storages_ids: List[int] = [prod_universal.storage.universal_storage_id for prod_universal in product_universal]

    if len(product_universal) < quantity_products:
        raise NotEnoughProducts("У данной категории недостаточно продуктов")

    await session_db.execute(
        update(UniversalStorage)
        .where(UniversalStorage.universal_storage_id.in_(storages_ids))
        .values(status=UniversalStorageStatus.RESERVED)
    )

    for id in storages_ids:
        new_purchase_request_universal = PurchaseRequestUniversal(
            purchase_request_id=purchase_request_id,
            universal_storage_id=id,
        )
        session_db.add(new_purchase_request_universal)

    return product_universal


async def _purchase_universal_one(
    result_check: ResultCheckCategory,
    user_id: int,
    promo_code_id: int,
    quantity_products: int,
    category_id: int,
):
    """Для покупки товара когда у категории стоит флаг allow_multiple_purchase"""

    product_full = await get_product_universal_by_category_id(category_id=category_id, get_full=True)
    if not product_full or not product_full[0]:
        raise UniversalProductNotFound()

    async with get_db() as session_db:
        async with session_db.begin():
            new_purchase_request = await create_new_purchase_request(
                session_db,
                user_id,
                promo_code_id,
                quantity_products,
                result_check.final_total
            )

            user = await write_off_of_funds(
                session_db,
                user_id,
                new_purchase_request.purchase_request_id,
                result_check.final_total
            )
            # после выхода из транзакции произойдёт commit()

        await filling_user(user)

    return StartPurchaseUniversalOne(
        purchase_request_id=new_purchase_request.purchase_request_id,
        category_id=category_id,
        promo_code_id=promo_code_id,
        full_product=product_full[0],
        translations_category=result_check.translations_category,
        original_price_one=result_check.category.price,
        purchase_price_one=result_check.final_total // quantity_products if result_check.final_total > 0 else result_check.final_total,
        cost_price_one=result_check.category.cost_price,
        total_amount=result_check.final_total,
        user_balance_before=result_check.user_balance_before,
        user_balance_after=user.balance,
        quantity_products=quantity_products
    )


async def _purchase_universal_different(
    result_check: ResultCheckCategory,
    user_id: int,
    promo_code_id: int,
    quantity_products: int,
    category_id: int,
    language: str
):
    """Для покупки товара когда у категории НЕ стоит флаг allow_multiple_purchase"""
    async with get_db() as session_db:
        async with session_db.begin():
            new_purchase_request = await create_new_purchase_request(
                session_db,
                user_id,
                promo_code_id,
                quantity_products,
                result_check.final_total
            )

            reserved_products = await _set_reserved_universal(
                session_db,
                category_id,
                quantity_products,
                new_purchase_request.purchase_request_id
            )

            full_reserved_products = [
                ProductUniversalFull.from_orm_model(product, language)
                for product in reserved_products
            ]

            user = await write_off_of_funds(
                session_db,
                user_id,
                new_purchase_request.purchase_request_id,
                result_check.final_total
            )
            # после выхода из транзакции произойдёт commit()

        await filling_user(user)

        # обновление redis
        await filling_product_universal_by_category()
        for prod_id in [product.product_universal_id for product in reserved_products]:
            await filling_universal_by_product_id(prod_id)
            await filling_all_keys_category()

    return StartPurchaseUniversal(
        purchase_request_id=new_purchase_request.purchase_request_id,
        category_id=category_id,
        promo_code_id=promo_code_id,
        media_type=full_reserved_products[0].universal_storage.media_type,
        full_reserved_products=full_reserved_products,
        translations_category=result_check.translations_category,
        original_price_one=result_check.category.price,
        purchase_price_one=result_check.final_total // quantity_products if result_check.final_total > 0 else result_check.final_total,
        cost_price_one=result_check.category.cost_price,
        total_amount=result_check.final_total,
        user_balance_before=result_check.user_balance_before,
        user_balance_after=user.balance
    )


async def start_purchase_universal(
    user_id: int,
    category_id: int,
    quantity_products: int,
    promo_code_id: Optional[int],
    language: str
) -> StartPurchaseUniversal | StartPurchaseUniversalOne:
    """
        Зафиксирует намерение покупки и заморозит деньги

        Проверяет баланс пользователя и наличие товара

        Создаёт:
        запись в PurchaseRequests (status=processing)
        запись в BalanceHolder (status=held)

        Резервирует нужные товары.
        Списывает деньги — удерживая (через BalanceHolder).

        :return: если категория хранит аккаунты, то StartPurchaseAccount, если хранит универсальные товары StartPurchaseUniversal
    """
    result_check = await check_category_and_money(user_id, category_id, quantity_products, promo_code_id)

    if result_check.category.allow_multiple_purchase:
        return await _purchase_universal_one(result_check, user_id, promo_code_id, quantity_products, category_id)

    return await _purchase_universal_different(result_check, user_id, promo_code_id, quantity_products, category_id, language)


