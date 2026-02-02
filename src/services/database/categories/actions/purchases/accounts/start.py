from typing import List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import NotEnoughAccounts
from src.services.database.categories.actions.purchases.general.start import write_off_of_funds, \
    create_new_purchase_request, check_category_and_money
from src.services.database.categories.models import ProductAccounts, AccountStorage, \
    StartPurchaseAccount, StorageStatus
from src.services.database.categories.models import PurchaseRequestAccount
from src.services.database.core.database import get_db
from src.services.redis.filling import filling_product_account_by_account_id, filling_user, filling_all_keys_category


async def _set_reserved_accounts(
    session_db: AsyncSession,
    category_id: int,
    quantity_products: int,
    purchase_request_id: int
) -> List[ProductAccounts]:
    """
    :param session_db: В транзакции
    """
    q = (
        select(ProductAccounts)
        .options(selectinload(ProductAccounts.account_storage))
        .join(ProductAccounts.account_storage)
        .where(
            (ProductAccounts.category_id == category_id) &
            (AccountStorage.status == StorageStatus.FOR_SALE)
        )
        .order_by(ProductAccounts.created_at.desc())
        .with_for_update()
        .limit(quantity_products)
    )
    result_db = await session_db.execute(q)
    product_accounts: List[ProductAccounts] = result_db.scalars().all()
    account_storages_ids: List[int] = [account.account_storage.account_storage_id for account in product_accounts]

    if len(product_accounts) < quantity_products:
        raise NotEnoughAccounts("У данной категории недостаточно аккаунтов")

    await session_db.execute(
        update(AccountStorage)
        .where(AccountStorage.account_storage_id.in_(account_storages_ids))
        .values(status=StorageStatus.RESERVED)
    )

    for id in account_storages_ids:
        new_purchase_request_account = PurchaseRequestAccount(
            purchase_request_id=purchase_request_id,
            account_storage_id=id,
        )
        session_db.add(new_purchase_request_account)

    return product_accounts


async def start_purchase_account(
    user_id: int,
    promo_code_id: int | None,
    quantity_products: int,
    category_id: int,
) -> StartPurchaseAccount:
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

    async with get_db() as session_db:
        async with session_db.begin():

            new_purchase_request = await create_new_purchase_request(
                session_db,
                user_id,
                promo_code_id,
                quantity_products,
                result_check.final_total
            )

            product_accounts = await _set_reserved_accounts(
                session_db,
                category_id,
                quantity_products,
                new_purchase_request.purchase_request_id
            )

            user = await write_off_of_funds(
                session_db,
                user_id,
                new_purchase_request.purchase_request_id,
                result_check.final_total
            )
            # после выхода из транзакции произойдёт commit()

        await filling_user(user)

        for ac_id in [account.account_id for account in product_accounts]:
            await filling_product_account_by_account_id(ac_id)

        await filling_all_keys_category(category_id)

    return StartPurchaseAccount(
        purchase_request_id = new_purchase_request.purchase_request_id,
        category_id = category_id,
        type_service_account = result_check.category.type_account_service,
        promo_code_id = promo_code_id,
        product_accounts = product_accounts,
        translations_category = result_check.translations_category,
        original_price_one = result_check.category.price,
        purchase_price_one = result_check.final_total // quantity_products if result_check.final_total > 0 else result_check.final_total,
        cost_price_one = result_check.category.cost_price,
        total_amount = result_check.final_total,
        user_balance_before = result_check.user_balance_before,
        user_balance_after = user.balance
    )