import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.services.database.categories.models import PurchaseRequests, AccountStorage, SoldAccounts, Purchases, \
    StorageStatus
from src.services.database.categories.models import StartPurchaseAccount
from src.services.database.categories.models import AccountServiceType
from src.services.database.core import get_db
from src.services.database.users.models.models_users import BalanceHolder


class TestFinalizePurchase:
    @pytest.mark.asyncio
    async def test_finalize_purchase_success_creates_sold_and_purchases_and_updates_states(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_product_account,
        create_promo_code,
        create_purchase_request,
        create_balance_holder,
        monkeypatch,
    ):
        """
        Успешное выполнение finalize_purchase:
        - move_file возвращает True (создаём temp файл),
        - rename_file возвращает True (перемещаем temp->final),
        - созданы SoldAccounts и Purchases,
        - AccountStorage.status == 'bought',
        - PurchaseRequests.status == 'completed', BalanceHolder.status == 'used',
        - publish_event вызван как для промокода, так и для purchase.account.
        """
        from src.services.database.categories.actions.purchases.accounts import finalize as finalize_mod
        from src.services.database.categories.actions.purchases.accounts.finalize import finalize_purchase_accounts

        # подготовка: пользователь, категория, продукт
        user = await create_new_user(balance=1000)
        cat = await create_category()
        promo = await create_promo_code()
        prod, prod_full = await create_product_account(category_id=cat.category_id)
        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=1,
            total_amount=prod_full.price if hasattr(prod_full, "price") else 0,
            status="processing"
        )
        balance_holder = await create_balance_holder(
            purchase_request_id=pr.purchase_request_id,
            user_id=user.user_id,
            amount=10,
            status="held"
        )

        # Подготовим fake move_file: при вызове создаёт temp файл (имитируем move(orig -> temp))
        async def fake_move_file(orig: str, temp: str):
            os.makedirs(os.path.dirname(temp), exist_ok=True)
            with open(temp, "wb") as f:
                f.write(b"fake")
            return True

        async def fake_rename_file(src: str, dst: str):
            # имитируем перемещение temp->final
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(src):
                os.replace(src, dst)
                return True
            return False

        # Собиратели вызовов
        publish_calls = []

        async def fake_publish_event(payload, topic):
            publish_calls.append((topic, payload))
            return True

        # Подмены
        monkeypatch.setattr(finalize_mod, "move_file", fake_move_file)
        monkeypatch.setattr(finalize_mod, "rename_file", fake_rename_file)
        monkeypatch.setattr(finalize_mod, "publish_event", fake_publish_event)

        data = StartPurchaseAccount(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.category_id,
            promo_code_id=promo.promo_code_id,
            product_accounts=[prod],
            type_service_account=AccountServiceType.TELEGRAM,
            translations_category=[],
            original_price_one=100,
            purchase_price_one=50,
            cost_price_one=10,
            total_amount=50,
            user_balance_before=user.balance,
            user_balance_after=user.balance - 50,
        )

        # Выполнение
        await finalize_purchase_accounts(user.user_id, data)

        # --- проверки БД ---
        async with get_db() as session:
            # SoldAccounts должен существовать
            q = await session.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
            sold = q.scalars().all()
            assert len(sold) >= 1

            # Purchases должен существовать для созданного sold_account
            q2 = await session.execute(select(Purchases).where(Purchases.user_id == user.user_id))
            purchases = q2.scalars().all()
            assert len(purchases) >= 1

            # AccountStorage статус -> 'bought'
            q3 = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id == prod.account_storage.account_storage_id))
            storage = q3.scalars().one()
            assert storage.status == StorageStatus.BOUGHT

            # PurchaseRequests.status == 'completed'
            db_pr = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert db_pr.status == "completed"

            # BalanceHolder.status == 'used'
            qb = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
            db_bh = qb.scalars().first()
            assert db_bh.status == "used"

        # publish_event должен был вызваться хотя бы дважды (promo activation + purchase.account)
        topics = [t for t, p in publish_calls]
        assert any("promo_code.activated" == t for t in topics)
        assert any("purchase.account" == t for t in topics)


    @pytest.mark.asyncio
    async def test_finalize_purchase_move_file_failure_calls_cancel_and_logs(
        self,
        patch_fake_aiogram,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Если move_file вернул False — должен вызвать send_log и cancel_purchase_request_accounts, и не создать SoldAccounts.
        Здесь мы мокируем cancel_purchase_request_accounts, чтобы проверить только факт вызова.
        """
        from src.services.database.categories.actions.purchases.accounts import finalize as finalize_mod
        from src.services.database.categories.actions.purchases.accounts.finalize import finalize_purchase_accounts

        user = await create_new_user()
        cat = await create_category()
        prod, _ = await create_product_account(category_id=cat.category_id)
        pr = await create_purchase_request(user_id=user.user_id, quantity=1, total_amount=0, status="processing")

        # move_file возвращает False (не удалось переместить первый файл)
        async def fake_move_file(orig, temp):
            return False

        called = {"cancel": False, "logged": False}

        async def fake_cancel(user_id, mapping, sold_account_ids, **kw):
            called["cancel"] = True

        async def fake_send_log(text):
            called["logged"] = True

        monkeypatch.setattr(finalize_mod, "move_file", fake_move_file)
        monkeypatch.setattr(finalize_mod, "cancel_purchase_request_accounts", fake_cancel)
        monkeypatch.setattr(finalize_mod, "send_log", fake_send_log)

        # заглушки для rename/fill/publish
        async def noop(*a, **kw): return None
        monkeypatch.setattr(finalize_mod, "publish_event", noop)

        data = StartPurchaseAccount(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.category_id,
            promo_code_id=None,
            product_accounts=[prod],
            type_service_account=AccountServiceType.TELEGRAM,
            translations_category=[],
            original_price_one=100,
            purchase_price_one=50,
            cost_price_one=10,
            total_amount=50,
            user_balance_before=user.balance,
            user_balance_after=user.balance,
        )

        await finalize_purchase_accounts(user.user_id, data)

        assert called["logged"] is True
        assert called["cancel"] is True

        # Проверим, что SoldAccounts не созданы
        async with get_db() as session:
            q = await session.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
            assert q.scalars().first() is None


    @pytest.mark.asyncio
    async def test_finalize_purchase_rename_failure_triggers_cancel_and_rolls_back(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        create_balance_holder,
        monkeypatch,
    ):
        """
        Если rename_file вернул False после успешного commit, finalize_purchase должен вызвать cancel_purchase_request_accounts.
        Здесь позволим cancel_purchase_request_accounts выполнить реальные откаты (не мокируем).
        После выполнения ожидаем, что SoldAccounts/Purchases удалены и PurchaseRequests.status == 'failed'
        """
        from src.services.database.categories.actions.purchases.accounts import finalize as finalize_mod
        from src.services.database.categories.actions.purchases.accounts.finalize import finalize_purchase_accounts

        user = await create_new_user()
        cat = await create_category()
        prod, prod_full = await create_product_account(category_id=cat.category_id)

        pr = await create_purchase_request(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
        balance_holder = await create_balance_holder(purchase_request_id=pr.purchase_request_id, user_id=user.user_id, amount=10, status="held")

        # move_file делает temp файл
        async def fake_move_file(orig: str, temp: str):
            os.makedirs(os.path.dirname(temp), exist_ok=True)
            with open(temp, "wb") as f:
                f.write(b"tempdata")
            return True

        # rename_file возвращает False (симулируем проблему при переименовании)
        async def fake_rename_file(src: str, dst: str):
            return False

        # Подменяем move/rename и заглушаем filling/publish
        monkeypatch.setattr(finalize_mod, "move_file", fake_move_file)
        monkeypatch.setattr(finalize_mod, "rename_file", fake_rename_file)

        data = SimpleNamespace(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.category_id,
            promo_code_id=None,
            product_accounts=[prod],
            type_service_account=AccountServiceType.TELEGRAM,
            translations_category=[],
            original_price_one=100,
            purchase_price_one=50,
            cost_price_one=10,
            total_amount=50,
            user_balance_before=user.balance,
            user_balance_after=user.balance - 50,
        )

        # Выполнение finalize — в теле rename_file вернёт False, finalize вызовет cancel_purchase_request_accounts (реальную)
        await finalize_purchase_accounts(user.user_id, data)

        # После этого SoldAccounts и Purchases должны быть удалены (cancel_purchase_request_accounts делает это)
        async with get_db() as session:
            q = await session.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
            assert q.scalars().first() is None

            q2 = await session.execute(select(Purchases).where(Purchases.user_id == user.user_id))
            assert q2.scalars().first() is None

            # PurchaseRequests должен быть помечен как failed
            pr_after = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert pr_after.status == "failed"

            # BalanceHolder должен быть released
            qbh = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
            bh_after = qbh.scalars().first()
            assert bh_after.status == "released"