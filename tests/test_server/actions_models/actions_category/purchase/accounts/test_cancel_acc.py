import os

import pytest
from sqlalchemy import select

from src.services.database.categories.models import PurchaseRequests, AccountStorage, ProductAccounts, SoldAccounts, \
    Purchases, StartPurchaseAccount
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.core import get_db
from src.services.database.users.models import Users
from src.services.database.users.models.models_users import BalanceHolder


class TestCancelPurchase:
    @pytest.mark.asyncio
    async def test_cancel_purchase_request_restores_files_and_db(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        create_balance_holder,
    ):
        """
        Проверяем:
        - файлы (temp -> orig, final -> orig) перемещаются обратно;
        - баланс пользователя увеличился на data.total_amount;
        - PurchaseRequests.status -> 'failed', BalanceHolder.status -> 'released';
        - AccountStorage.status -> 'for_sale';
        - ProductAccounts строки восстановлены (если их удалить заранее).
        """
        from src.services.database.categories.actions.purchases.accounts.cancel import cancel_purchase_request_accounts

        # подготовка: пользователь
        user = await create_new_user(balance=100)
        # подготовка: категория и продукт (product + product_full)
        cat = await create_category()
        prod, prod_full = await create_product_account(category_id=cat.category_id)
        pr = await create_purchase_request(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
        balance_holder = await create_balance_holder(
            purchase_request_id=pr.purchase_request_id, user_id=user.user_id, amount=50, status="held"
        )

        # Создаём mapping: temp -> orig (создаём temp файл)
        orig = tmp_path / "orig_dir" / "account.enc"
        temp = tmp_path / "temp_dir" / "account.enc"
        # создадим temp файл, final отсутствует
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(b"fake-enc")

        mapping = [(str(orig), str(temp), None)]

        # Для проверки ветки восстановления ProductAccounts: удалим строку ProductAccounts из БД,
        # чтобы функция добавила её заново (эта ветка находится в коде)
        async with get_db() as session:
            await session.execute(
                ProductAccounts.__table__.delete().where(ProductAccounts.account_id == prod.account_id)
            )
            await session.commit()

        data = StartPurchaseAccount(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.category_id,
            promo_code_id=None,
            product_accounts=[prod],  # с загруженным account_storage
            type_service_account=AccountServiceType.TELEGRAM,
            translations_category=[],
            original_price_one=100,
            purchase_price_one=50,
            cost_price_one=10,
            total_amount=50,
            user_balance_before=user.balance,
            user_balance_after=user.balance + 50
        )

        # Вызов
        await cancel_purchase_request_accounts(
            user_id=user.user_id,
            category_id=cat.category_id,
            mapping=mapping,
            sold_account_ids=[],
            purchase_ids=[],
            total_amount=data.total_amount,
            purchase_request_id=data.purchase_request_id,
            product_accounts=data.product_accounts,
            type_service_account=data.type_service_account
        )

        # --- проверки файлов ---
        # orig должен существовать, temp — удалён
        assert os.path.exists(str(orig))
        assert not os.path.exists(str(temp))

        # --- проверки БД ---
        async with get_db() as session:
            # баланс пользователя увеличен на total_amount
            db_user = await session.get(Users, user.user_id)
            assert db_user.balance == 100 + data.total_amount

            # PurchaseRequests.status == 'failed'
            db_pr = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert db_pr.status == "failed"

            # BalanceHolder.status == 'released'
            q = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
            db_bh = q.scalars().first()
            assert db_bh.status == "released"

            # AccountStorage status -> 'for_sale' for involved accounts
            account_storage_id = prod.account_storage.account_storage_id
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id == account_storage_id))
            storage = q.scalars().one()
            assert storage.status == "for_sale"

            # ProductAccounts row был восстановлен (т.к. мы удаляли её заранее)
            q = await session.execute(select(ProductAccounts).where(ProductAccounts.account_storage_id == account_storage_id))
            restored = q.scalars().first()
            assert restored is not None


    @pytest.mark.asyncio
    async def test_cancel_purchase_request_deletes_sold_accounts_and_restores(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_product_account,
        create_sold_account,
        create_purchase,
        create_purchase_request,
        create_balance_holder,
    ):
        """
        Проверяем что:
        - SoldAccounts и Purchases удаляются при передаче sold_account_ids
        - остальные восстановительные операции тоже выполняются
        """
        from src.services.database.categories.actions.purchases.accounts.cancel import cancel_purchase_request_accounts

        user = await create_new_user(balance=200)
        cat = await create_category()

        # product для data.products
        prod, prod_full = await create_product_account(category_id=cat.category_id)
        _, sold = await create_sold_account(
            owner_id=user.user_id,
            type_account_service=prod.type_account_service
        )
        pa = await create_purchase(
            user_id=user.user_id,
            account_storage_id=sold.account_storage.account_storage_id,
            original_price=120,
            purchase_price=120,
            cost_price=100,
            net_profit=10
        )
        pr = await create_purchase_request(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
        balance_holder = await create_balance_holder(
            purchase_request_id=pr.purchase_request_id, user_id=user.user_id, amount=30, status="held"
        )

        # mapping: create temp file to be moved back
        orig = tmp_path / "orig2" / "a.enc"
        temp = tmp_path / "temp2" / "a.enc"
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(b"data")
        mapping = [(str(orig), str(temp), None)]

        data = StartPurchaseAccount(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.category_id,
            promo_code_id=None,
            product_accounts=[prod],
            type_service_account=AccountServiceType.TELEGRAM,
            translations_category=[],
            original_price_one=100,
            purchase_price_one=30,
            cost_price_one=10,
            total_amount=30,
            user_balance_before=user.balance,
            user_balance_after=user.balance + 30
        )

        # вызов с sold_account_ids
        await cancel_purchase_request_accounts(
            user_id=user.user_id,
            category_id=cat.category_id,
            mapping=mapping,
            sold_account_ids=[sold.sold_account_id],
            purchase_ids=[pa.purchase_id],
            total_amount=data.total_amount,
            purchase_request_id=data.purchase_request_id,
            product_accounts=data.product_accounts,
            type_service_account=data.type_service_account
        )

        # проверки
        # файл перемещён
        assert os.path.exists(str(orig))
        assert not os.path.exists(str(temp))

        async with get_db() as session:
            # SoldAccounts удалены
            q = await session.execute(select(SoldAccounts).where(SoldAccounts.account_storage_id == sold.account_storage.account_storage_id))
            assert q.scalars().first() is None

            # Purchases удалены
            q = await session.execute(select(Purchases).where(Purchases.account_storage_id == sold.account_storage.account_storage_id))
            assert q.scalars().first() is None

            # PurchaseRequests status / BalanceHolder status
            db_pr = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert db_pr.status == "failed"
            q = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
            db_bh = q.scalars().first()
            assert db_bh.status == "released"

            # AccountStorage status -> for_sale
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id == prod.account_storage.account_storage_id))
            storage = q.scalars().one()
            assert storage.status == "for_sale"
