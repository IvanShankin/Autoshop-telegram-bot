import orjson
import pytest
from sqlalchemy import select

from src.exceptions import NotEnoughAccounts, NotEnoughMoney
from src.services.database.categories.models import ProductAccountFull
from src.services.database.categories.models import PurchaseRequests, PurchaseRequestAccount, \
    AccountStorage, ProductAccounts
from src.services.database.core import get_db
from src.services.database.users.models import Users
from src.services.database.users.models.models_users import BalanceHolder
from src.services.redis.core_redis import get_redis
from tests.helpers.helper_functions import comparison_models


class TestStartPurchaseRequest:
    @pytest.mark.asyncio
    async def test_start_purchase_request_success(
        self,
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_category,
        create_product_account,
    ):
        """
        Успешный старт покупки:
        - создаётся PurchaseRequests (status=processing)
        - создаются PurchaseRequestAccount (кол-во = quantity_accounts)
        - создаётся BalanceHolder
        - списывается баланс пользователя
        - AccountStorage.status -> 'reserved' для задействованных аккаунтов
        - возвращаемый StartPurchaseAccount содержит согласованные поля
        """
        from src.services.database.categories.actions.purchases.main_purchase import start_purchase_account
        # подготовка
        user = await create_new_user(balance=10_000)
        full_category = await create_category(price=100)
        category_id = full_category.category_id
        quantity = 3

        # создаём required number of product accounts in that category
        created_products: list[ProductAccounts] = []
        created_products_full: list[ProductAccounts] = []
        for _ in range(quantity):
            prod, prod_full = await create_product_account(category_id=category_id)
            created_products.append(prod)
            created_products_full.append(prod_full)

        async with get_db() as session:
            db_user = await session.get(Users, user.user_id)
            balance_before = db_user.balance

        # вызов тестируемой функции
        result = await start_purchase_account(
            user_id=user.user_id,
            category_id=category_id,
            quantity_products=quantity,
            promo_code_id=None
        )

        result_product_accounts: list[dict] = [account.to_dict() for account in result.product_accounts]

        # проверки возвращаемых данных (базовые)
        assert result.total_amount >= 0
        assert result.category_id == category_id
        assert len(result.product_accounts) == quantity
        assert result.purchase_request_id is not None
        assert result.user_balance_before == balance_before
        assert result.user_balance_after == balance_before - result.total_amount
        for account in created_products:
            assert account.to_dict() in result_product_accounts


        # проверки в БД
        async with get_db() as session:
            # PurchaseRequests
            pr = await session.get(PurchaseRequests, result.purchase_request_id)
            assert pr is not None
            assert pr.status == "processing"
            assert pr.quantity == quantity
            # PurchaseRequestAccount count
            q = await session.execute(
                select(PurchaseRequestAccount).where(PurchaseRequestAccount.purchase_request_id == pr.purchase_request_id)
            )
            pr_accounts = q.scalars().all()
            assert len(pr_accounts) == quantity

            # BalanceHolder
            q = await session.execute(
                select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id)
            )
            bal_holder = q.scalars().first()
            assert bal_holder is not None
            assert bal_holder.amount == result.total_amount

            # AccountStorage статусы должны быть "reserved" для соответствующих хранилищ
            # Мы собираем идентификаторы из возвращенных product_accounts
            storage_ids = [p.account_storage.account_storage_id for p in result.product_accounts]
            q = await session.execute(
                select(AccountStorage).where(AccountStorage.account_storage_id.in_(storage_ids))
            )
            storages = q.scalars().all()
            assert all(s.status == "reserved" for s in storages)

            # баланс должен уменьшится
            db_user_after = await session.get(Users, user.user_id)
            assert db_user_after.balance == balance_before - result.total_amount

        async with get_redis() as session_redis:
            user_dict = orjson.loads(await session_redis.get(f'user:{user.user_id}'))
            assert comparison_models(db_user_after.to_dict(), user_dict)

            for account in created_products_full:
                account.account_storage.status = "reserved" # аккаунт должен стать зарезервированным
                account_redis = await session_redis.get(f'product_account:{account.account_id}')
                assert not account_redis


    @pytest.mark.asyncio
    async def test_start_purchase_request_with_promo_code(
        self,
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_category,
        create_product_account,
        create_promo_code,
    ):
        """
        Проверяет корректную работу функции start_purchase_account с применением промокода:
        - скидка применяется (total_amount уменьшен)
        - создаётся PurchaseRequests с промокодом
        - баланс списывается с учётом скидки
        """
        from src.services.database.categories.actions.purchases.main_purchase import start_purchase_account

        # подготовка данных
        user = await create_new_user(balance=10_000)
        category = await create_category(price=500)
        promo = await create_promo_code()

        quantity = 2
        for _ in range(quantity):
            await create_product_account(category_id=category.category_id)

        async with get_db() as session:
            db_user = await session.get(Users, user.user_id)
            balance_before = db_user.balance

        # вызов тестируемой функции
        result = await start_purchase_account(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=quantity,
            promo_code_id=promo.promo_code_id,
        )

        # проверки возвращаемых данных
        assert result.category_id == category.category_id
        assert result.purchase_request_id is not None
        assert result.total_amount < category.price * quantity  # скидка применена
        assert result.user_balance_after == balance_before - result.total_amount

        # проверки в БД
        async with get_db() as session:
            pr = await session.get(PurchaseRequests, result.purchase_request_id)
            assert pr is not None
            assert pr.promo_code_id == promo.promo_code_id  # промокод записан
            db_user_after = await session.get(Users, user.user_id)
            assert db_user_after.balance == balance_before - result.total_amount


    @pytest.mark.asyncio
    async def test_start_purchase_request_not_enough_accounts(
        self,
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_category,
        create_product_account,
    ):
        """
        Если в категории меньше аккаунтов, чем требуется — возникает NotEnoughAccounts.
        """
        from src.services.database.categories.actions.purchases.main_purchase import start_purchase_account
        user = await create_new_user(balance=10000)
        full_category = await create_category()
        category_id = full_category.category_id

        # создаём только 1 аккаунт, а запросим 5
        await create_product_account(category_id=category_id)
        with pytest.raises(NotEnoughAccounts):
            await start_purchase_account(
                user_id=user.user_id,
                category_id=category_id,
                quantity_products=5,
                promo_code_id=None
            )


    @pytest.mark.asyncio
    async def test_start_purchase_request_not_enough_money(
        self,
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_category,
        create_product_account,
    ):
        """
        Если у пользователя не хватает денег — возникает NotEnoughMoney.
        """
        from src.services.database.categories.actions.purchases.main_purchase import start_purchase_account
        user = await create_new_user(balance=10)  # маленький баланс
        full_category = await create_category(price=1000)
        category_id = full_category.category_id

        # создаём хотя бы 1 аккаунт
        await create_product_account(category_id=category_id)

        with pytest.raises(NotEnoughMoney):
            await start_purchase_account(
                user_id=user.user_id,
                category_id=category_id,
                quantity_products=1,
                promo_code_id=None
            )
