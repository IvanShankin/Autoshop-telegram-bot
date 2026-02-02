import os

import pytest
from sqlalchemy import select

from src.services.database.categories.models import PurchaseRequests, Purchases
from src.services.database.categories.models import (
    UniversalStorage,
    StorageStatus,
    ProductUniversal,
    SoldUniversal,
)
from src.services.database.core import get_db
from src.services.database.users.models import Users
from src.services.database.users.models.models_users import BalanceHolder


class TestCancelPurchaseUniversalDifferent:
    @pytest.mark.asyncio
    async def test_cancel_purchase_universal_different_restores_files_and_db(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_product_universal,
        create_purchase_request,
        create_balance_holder,
    ):
        """
        Проверяем:
        - файл возвращается temp -> orig;
        - баланс пользователя увеличен на total_amount;
        - PurchaseRequests.status -> 'failed', BalanceHolder.status -> 'released';
        - UniversalStorage.status -> FOR_SALE;
        - ProductUniversal строка восстановлена, если её удалить заранее.
        """
        from src.services.database.categories.actions.purchases.universal.cancel import (
            cancel_purchase_universal_different,
        )

        # --- подготовка ---
        user = await create_new_user(balance=100)
        category = await create_category()
        storage, product_full = await create_product_universal(
            category_id=category.category_id
        )

        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=1,
            total_amount=50,
            status="processing",
        )

        await create_balance_holder(
            purchase_request_id=pr.purchase_request_id,
            user_id=user.user_id,
            amount=50,
            status="held",
        )

        # --- mapping: temp -> orig ---
        orig = tmp_path / "orig_dir" / "universal.enc"
        temp = tmp_path / "temp_dir" / "universal.enc"
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(b"encrypted-data")

        mapping = [(str(orig), str(temp), str(orig))]

        # --- удаляем ProductUniversal, чтобы проверить восстановление ---
        async with get_db() as session:
            await session.execute(
                ProductUniversal.__table__.delete().where(
                    ProductUniversal.universal_storage_id == storage.universal_storage_id
                )
            )
            await session.commit()

        # --- вызов ---
        await cancel_purchase_universal_different(
            user_id=user.user_id,
            category_id=category.category_id,
            mapping=mapping,
            sold_universal_ids=[],
            purchase_ids=[],
            total_amount=50,
            purchase_request_id=pr.purchase_request_id,
            product_universal=[product_full],
        )

        # --- проверки файлов ---
        assert os.path.exists(str(orig))
        assert not os.path.exists(str(temp))

        # --- проверки БД ---
        async with get_db() as session:
            # баланс возвращён
            db_user = await session.get(Users, user.user_id)
            assert db_user.balance == 150

            # PurchaseRequests.status
            db_pr = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert db_pr.status == "failed"

            # BalanceHolder.status
            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().first()
            assert bh.status == "released"

            # UniversalStorage.status -> FOR_SALE
            us = await session.get(UniversalStorage, storage.universal_storage_id)
            assert us.status == StorageStatus.FOR_SALE
            assert us.original_filename is not None

            # ProductUniversal восстановлен
            q = await session.execute(
                select(ProductUniversal).where(
                    ProductUniversal.universal_storage_id == storage.universal_storage_id
                )
            )
            restored = q.scalars().first()
            assert restored is not None


    @pytest.mark.asyncio
    async def test_cancel_purchase_universal_different_deletes_sold_and_purchases(
        self,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_category,
        create_product_universal,
        create_sold_universal,
        create_purchase,
        create_purchase_request,
        create_balance_holder,
    ):
        """
        Проверяем:
        - SoldUniversal и Purchases удаляются, если переданы их id;
        - остальные восстановительные операции выполняются.
        """
        from src.services.database.categories.actions.purchases.universal.cancel import (
            cancel_purchase_universal_different,
        )

        user = await create_new_user(balance=200)
        category = await create_category()

        storage, product_full = await create_product_universal(
            category_id=category.category_id
        )

        sold, _ = await create_sold_universal(
            owner_id=user.user_id,
            universal_storage_id=storage.universal_storage_id,
        )

        purchase = await create_purchase(
            user_id=user.user_id,
            universal_storage_id=storage.universal_storage_id,
            original_price=120,
            purchase_price=120,
            cost_price=80,
            net_profit=40,
        )

        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=1,
            total_amount=60,
            status="processing",
        )

        await create_balance_holder(
            purchase_request_id=pr.purchase_request_id,
            user_id=user.user_id,
            amount=60,
            status="held",
        )

        # mapping
        orig = tmp_path / "orig2" / "u.enc"
        temp = tmp_path / "temp2" / "u.enc"
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(b"data")

        mapping = [(str(orig), str(temp), str(orig))]

        # вызов
        await cancel_purchase_universal_different(
            user_id=user.user_id,
            category_id=category.category_id,
            mapping=mapping,
            sold_universal_ids=[sold.sold_universal_id],
            purchase_ids=[purchase.purchase_id],
            total_amount=60,
            purchase_request_id=pr.purchase_request_id,
            product_universal=[product_full],
        )

        # файл восстановлен
        assert os.path.exists(str(orig))
        assert not os.path.exists(str(temp))

        async with get_db() as session:
            # SoldUniversal удалён
            q = await session.execute(
                select(SoldUniversal).where(
                    SoldUniversal.universal_storage_id == storage.universal_storage_id
                )
            )
            assert q.scalars().first() is None

            # Purchases удалены
            q = await session.execute(
                select(Purchases).where(
                    Purchases.universal_storage_id == storage.universal_storage_id
                )
            )
            assert q.scalars().first() is None

            # статус заявки
            db_pr = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert db_pr.status == "failed"

            # статус холдера
            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().first()
            assert bh.status == "released"

            # UniversalStorage -> FOR_SALE
            us = await session.get(UniversalStorage, storage.universal_storage_id)
            assert us.status == StorageStatus.FOR_SALE
