import os
from pathlib import Path

import pytest
from sqlalchemy import select

from src.services.database.core import get_db
from src.services.database.categories.models import (
    PurchaseRequests,
    Purchases,
)
from src.services.database.categories.models.product_universal import (
    UniversalStorage,
    UniversalStorageStatus,
    SoldUniversal,
    PurchaseRequestUniversal, ProductUniversal, UniversalMediaType,
)
from src.services.database.users.models.models_users import BalanceHolder
from src.services.database.categories.models.shemas.purshanse_schem import (
    StartPurchaseUniversalOne, StartPurchaseUniversal,
)


class TestFinalizePurchaseUniversalOne:
    @pytest.mark.asyncio
    async def test_finalize_purchase_universal_one_success(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_universal_storage,
        create_product_universal,
        create_purchase_request,
        create_balance_holder,
        monkeypatch,
    ):
        """
        Успешное выполнение finalize_purchase_universal_one:
        - копирование файлов выполнено,
        - созданы UniversalStorage (BOUGHT),
        - созданы SoldUniversal и Purchases,
        - создан PurchaseRequestUniversal,
        - PurchaseRequests.status == completed,
        - BalanceHolder.status == used,
        - publish_event вызван.
        """
        from src.services.database.categories.actions.purchases.universal.finalize import (
            finalize_purchase_universal_one,
        )
        import src.services.database.categories.actions.purchases.universal.finalize as finalize_mod

        # --- данные ---
        user = await create_new_user(balance=1000)
        category = await create_category(allow_multiple_purchase=True)

        storage, product_full = await create_product_universal(
            category_id=category.category_id
        )

        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=2,
            total_amount=200,
            status="processing",
        )

        await create_balance_holder(
            purchase_request_id=pr.purchase_request_id,
            user_id=user.user_id,
            amount=200,
            status="held",
        )

        # --- mocks ---
        # copy_file просто создаёт файл
        def fake_copy_file(src, dst_dir, file_name):
            os.makedirs(dst_dir, exist_ok=True)
            with open(os.path.join(dst_dir, file_name), "wb") as f:
                f.write(b"data")

        publish_calls = []

        async def fake_publish_event(payload, topic):
            publish_calls.append(topic)

        async def noop(*a, **kw):
            return None

        monkeypatch.setattr(finalize_mod, "copy_file", fake_copy_file)
        monkeypatch.setattr(finalize_mod, "publish_event", fake_publish_event)
        monkeypatch.setattr(finalize_mod, "filling_product_universal_by_category", noop)
        monkeypatch.setattr(finalize_mod, "filling_sold_universal_by_owner_id", noop)
        monkeypatch.setattr(finalize_mod, "filling_universal_by_product_id", noop)
        monkeypatch.setattr(finalize_mod, "filling_sold_universal_by_universal_id", noop)

        data = StartPurchaseUniversalOne(
            purchase_request_id=pr.purchase_request_id,
            category_id=category.category_id,
            promo_code_id=None,
            full_product=product_full,
            quantity_products=2,
            original_price_one=150,
            purchase_price_one=100,
            cost_price_one=40,
            total_amount=200,
            user_balance_before=user.balance,
            user_balance_after=user.balance - 200,
            translations_category=[],
        )

        # --- выполнение ---
        result = await finalize_purchase_universal_one(user.user_id, data)
        assert result is True

        # --- проверки БД ---
        async with get_db() as session:
            # UniversalStorage (BOUGHT)
            q = await session.execute(
                select(UniversalStorage).where(
                    UniversalStorage.status == UniversalStorageStatus.BOUGHT
                )
            )
            storages = q.scalars().all()
            assert len(storages) == 2

            # SoldUniversal
            q = await session.execute(
                select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id)
            )
            sold = q.scalars().all()
            assert len(sold) == 2

            # Purchases
            q = await session.execute(
                select(Purchases).where(Purchases.user_id == user.user_id)
            )
            purchases = q.scalars().all()
            assert len(purchases) == 2

            # PurchaseRequestUniversal
            q = await session.execute(
                select(PurchaseRequestUniversal).where(
                    PurchaseRequestUniversal.purchase_request_id == pr.purchase_request_id
                )
            )
            pru = q.scalars().all()
            assert len(pru) == 2

            # PurchaseRequests.status
            pr_db = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert pr_db.status == "completed"

            # BalanceHolder.status
            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().one()
            assert bh.status == "used"

        assert "purchase.universal" in publish_calls


    @pytest.mark.asyncio
    async def test_finalize_purchase_universal_one_exception_triggers_cancel(
        self,
        patch_fake_aiogram,
        create_new_user,
        create_category,
        create_product_universal,
        create_purchase_request,
        create_balance_holder,
        monkeypatch,
    ):
        """
        Если в процессе finalize возникает исключение —
        вызывается cancel_purchase_universal_one,
        данные в БД не остаются.
        """
        from src.services.database.categories.actions.purchases.universal.finalize import (
            finalize_purchase_universal_one,
        )
        import src.services.database.categories.actions.purchases.universal.finalize as finalize_mod

        user = await create_new_user(balance=1000)
        category = await create_category(allow_multiple_purchase=True)
        storage, product_full = await create_product_universal(
            category_id=category.category_id
        )

        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=1,
            total_amount=100,
            status="processing",
        )

        await create_balance_holder(
            purchase_request_id=pr.purchase_request_id,
            user_id=user.user_id,
            amount=100,
            status="held",
        )

        # copy_file падает
        def broken_copy(*a, **kw):
            raise RuntimeError("FS error")

        called = {"cancel": False}

        async def fake_cancel(**kw):
            called["cancel"] = True

        monkeypatch.setattr(finalize_mod, "copy_file", broken_copy)
        monkeypatch.setattr(finalize_mod, "cancel_purchase_universal_one", fake_cancel)

        data = StartPurchaseUniversalOne(
            purchase_request_id=pr.purchase_request_id,
            category_id=category.category_id,
            promo_code_id=None,
            full_product=product_full,
            quantity_products=1,
            original_price_one=100,
            purchase_price_one=100,
            cost_price_one=40,
            total_amount=100,
            user_balance_before=user.balance,
            user_balance_after=user.balance - 100,
            translations_category=[],
        )

        result = await finalize_purchase_universal_one(user.user_id, data)
        assert result is False
        assert called["cancel"] is True

        # --- БД чистая ---
        async with get_db() as session:
            q = await session.execute(
                select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id)
            )
            assert q.scalars().first() is None

            q = await session.execute(
                select(Purchases).where(Purchases.user_id == user.user_id)
            )
            assert q.scalars().first() is None

            pr_db = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert pr_db.status != "completed"


class TestFinalizePurchaseUniversalDifferent:
    @pytest.mark.asyncio
    async def test_finalize_purchase_universal_different_success(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_universal_storage,
        create_product_universal,
        create_purchase_request,
        create_balance_holder,
        monkeypatch,
    ):
        """
        Успешный сценарий:
        - move_file OK
        - DB транзакция OK
        - rename_file OK
        - SoldUniversal, Purchases созданы
        - ProductUniversal удалён
        - UniversalStorage.status == BOUGHT
        - PurchaseRequests.status == completed
        - BalanceHolder.status == used
        - publish_event вызван
        """
        from src.services.database.categories.actions.purchases.universal.finalize import (
            finalize_purchase_universal_different,
        )
        import src.services.database.categories.actions.purchases.universal.finalize as finalize_mod

        user = await create_new_user(balance=1000)
        category = await create_category(allow_multiple_purchase=False)

        products = []
        for _ in range(2):
            storage, full = await create_product_universal(category_id=category.category_id)
            products.append(full)

        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=2,
            total_amount=200,
            status="processing",
        )

        await create_balance_holder(
            purchase_request_id=pr.purchase_request_id,
            user_id=user.user_id,
            amount=200,
            status="held",
        )

        # --- mocks ---
        async def fake_move_file(orig, temp):
            os.makedirs(Path(temp).parent, exist_ok=True)
            with open(temp, "wb") as f:
                f.write(b"temp")
            return True

        async def fake_rename_file(src, dst):
            os.makedirs(Path(dst).parent, exist_ok=True)
            os.replace(src, dst)
            return True

        publish_calls = []

        async def fake_publish_event(payload, topic):
            publish_calls.append(topic)

        async def noop(*a, **kw):
            return None

        monkeypatch.setattr(finalize_mod, "move_file", fake_move_file)
        monkeypatch.setattr(finalize_mod, "rename_file", fake_rename_file)
        monkeypatch.setattr(finalize_mod, "publish_event", fake_publish_event)
        monkeypatch.setattr(finalize_mod, "filling_product_universal_by_category", noop)
        monkeypatch.setattr(finalize_mod, "filling_sold_universal_by_owner_id", noop)
        monkeypatch.setattr(finalize_mod, "filling_universal_by_product_id", noop)
        monkeypatch.setattr(finalize_mod, "filling_sold_universal_by_universal_id", noop)

        data = StartPurchaseUniversal(
            purchase_request_id=pr.purchase_request_id,
            category_id=category.category_id,
            promo_code_id=None,
            full_reserved_products=products,
            original_price_one=150,
            purchase_price_one=100,
            cost_price_one=40,
            total_amount=200,
            user_balance_before=user.balance,
            user_balance_after=user.balance - 200,
            translations_category=[],
            media_type=UniversalMediaType.DOCUMENT,
        )

        result = await finalize_purchase_universal_different(user.user_id, data)
        assert result is True

        async with get_db() as session:
            # SoldUniversal
            q = await session.execute(
                select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id)
            )
            sold = q.scalars().all()
            assert len(sold) == 2

            # Purchases
            q = await session.execute(
                select(Purchases).where(Purchases.user_id == user.user_id)
            )
            purchases = q.scalars().all()
            assert len(purchases) == 2

            # ProductUniversal удалён
            q = await session.execute(select(ProductUniversal))
            assert q.scalars().first() is None

            # UniversalStorage BOUGHT
            q = await session.execute(select(UniversalStorage))
            storages = q.scalars().all()
            assert all(s.status == UniversalStorageStatus.BOUGHT for s in storages)

            # PurchaseRequests
            pr_db = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert pr_db.status == "completed"

            # BalanceHolder
            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().one()
            assert bh.status == "used"

        assert "purchase.universal" in publish_calls


    @pytest.mark.asyncio
    async def test_move_file_failure_triggers_cancel(
        self,
        patch_fake_aiogram,
        create_new_user,
        create_category,
        create_product_universal,
        create_purchase_request,
        create_balance_holder,
        monkeypatch,
    ):
        """
        move_file вернул False → send_log + cancel_purchase_universal_different,
        DB изменения не применяются.
        """
        from src.services.database.categories.actions.purchases.universal.finalize import (
            finalize_purchase_universal_different,
        )
        import src.services.database.categories.actions.purchases.universal.finalize as finalize_mod

        user = await create_new_user()
        category = await create_category()

        _, product = await create_product_universal(category_id=category.category_id)

        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=1,
            total_amount=100,
            status="processing",
        )

        await create_balance_holder(
            purchase_request_id=pr.purchase_request_id,
            user_id=user.user_id,
            amount=100,
            status="held",
        )

        async def fail_move(*a, **kw):
            return False

        called = {"cancel": False, "log": False}

        async def fake_cancel(**kw):
            called["cancel"] = True

        async def fake_send_log(*a, **kw):
            called["log"] = True

        monkeypatch.setattr(finalize_mod, "move_file", fail_move)
        monkeypatch.setattr(finalize_mod, "cancel_purchase_universal_different", fake_cancel)
        monkeypatch.setattr(finalize_mod, "send_log", fake_send_log)

        data = StartPurchaseUniversal(
            purchase_request_id=pr.purchase_request_id,
            category_id=category.category_id,
            promo_code_id=None,
            full_reserved_products=[product],
            original_price_one=100,
            purchase_price_one=100,
            cost_price_one=40,
            total_amount=100,
            user_balance_before=user.balance,
            user_balance_after=user.balance,
            translations_category=[],
            media_type=UniversalMediaType.DOCUMENT,
        )

        result = await finalize_purchase_universal_different(user.user_id, data)
        assert result is False
        assert called["cancel"] is True
        assert called["log"] is True


    @pytest.mark.asyncio
    async def test_rename_file_failure_after_commit_rolls_back(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_product_universal,
        create_purchase_request,
        create_balance_holder,
        monkeypatch,
    ):
        """
        rename_file = False после commit →
        cancel_purchase_universal_different откатывает DB.
        """
        from src.services.database.categories.actions.purchases.universal.finalize import (
            finalize_purchase_universal_different,
        )
        import src.services.database.categories.actions.purchases.universal.finalize as finalize_mod

        user = await create_new_user()
        category = await create_category()

        _, product = await create_product_universal(category_id=category.category_id)

        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=1,
            total_amount=100,
            status="processing",
        )

        await create_balance_holder(
            purchase_request_id=pr.purchase_request_id,
            user_id=user.user_id,
            amount=100,
            status="held",
        )

        async def ok_move(orig, temp):
            os.makedirs(Path(temp).parent, exist_ok=True)
            with open(temp, "wb") as f:
                f.write(b"x")
            return True

        async def fail_rename(*a, **kw):
            return False

        monkeypatch.setattr(finalize_mod, "move_file", ok_move)
        monkeypatch.setattr(finalize_mod, "rename_file", fail_rename)

        data = StartPurchaseUniversal(
            purchase_request_id=pr.purchase_request_id,
            category_id=category.category_id,
            promo_code_id=None,
            full_reserved_products=[product],
            original_price_one=100,
            purchase_price_one=100,
            cost_price_one=40,
            total_amount=100,
            user_balance_before=user.balance,
            user_balance_after=user.balance - 100,
            translations_category=[],
            media_type=UniversalMediaType.DOCUMENT,
        )

        result = await finalize_purchase_universal_different(user.user_id, data)
        assert result is False

        async with get_db() as session:
            # SoldUniversal откатился
            q = await session.execute(
                select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id)
            )
            assert q.scalars().first() is None

            # Purchases откатились
            q = await session.execute(
                select(Purchases).where(Purchases.user_id == user.user_id)
            )
            assert q.scalars().first() is None

            # PurchaseRequests.failed
            pr_db = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert pr_db.status == "failed"

            # BalanceHolder released
            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().one()
            assert bh.status == "released"