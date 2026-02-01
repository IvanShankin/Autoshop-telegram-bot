import os
from typing import List

import pytest
from sqlalchemy import select

from src.services.database.categories.models import PurchaseRequests, Purchases
from src.services.database.categories.models.main_category_and_product import ProductType
from src.services.database.categories.models.product_universal import (
    SoldUniversal,
    UniversalStorage,
    UniversalStorageStatus,
)
from src.services.database.core import get_db
from src.services.database.users.models import Users
from src.services.database.users.models.models_users import BalanceHolder


class TestDifferentPurchase:
    @pytest.mark.asyncio
    async def test_purchase_universal_success_different(
        self,
        patch_fake_aiogram,
        monkeypatch,
        create_new_user,
        create_category,
        create_universal_storage,
        create_product_universal,
    ):
        """
        Интеграционный тест:
        - покупка universal (different) проходит успешно;
        - создаются SoldUniversal / Purchases;
        - PurchaseRequests.status -> completed, BalanceHolder.status -> used;
        - UniversalStorage.status -> bought;
        - файлы перемещены в финальный путь.
        """
        from src.services.filesystem.media_paths import create_path_universal_storage
        from src.services.database.categories.actions.purchases.main_purchase import purchase_universal

        user = await create_new_user(balance=10_000)
        category = await create_category(price=200)
        category_id = category.category_id
        quantity = 2

        products = []
        for _ in range(quantity):
            storage, product = await create_product_universal(category_id=category_id)
            products.append(product)


        result = await purchase_universal(
            user_id=user.user_id,
            category_id=category_id,
            quantity_products=quantity,
            language="ru",
            promo_code_id=None,
        )

        assert result is True

        async with get_db() as session:
            # PurchaseRequest
            q = await session.execute(
                select(PurchaseRequests)
                .where(PurchaseRequests.user_id == user.user_id)
                .order_by(PurchaseRequests.purchase_request_id.desc())
            )
            pr = q.scalars().first()
            assert pr is not None
            assert pr.status == "completed"

            # BalanceHolder
            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().first()
            assert bh is not None
            assert bh.status == "used"

            # SoldUniversal
            q = await session.execute(
                select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id)
            )
            sold = q.scalars().all()
            assert len(sold) == quantity

            # Purchases
            q = await session.execute(
                select(Purchases).where(Purchases.user_id == user.user_id)
            )
            purchases = q.scalars().all()
            assert len(purchases) >= quantity

            # UniversalStorage.status -> bought
            storage_ids = [p.universal_storage_id for p in products]
            q = await session.execute(
                select(UniversalStorage).where(
                    UniversalStorage.universal_storage_id.in_(storage_ids)
                )
            )
            storages = q.scalars().all()
            assert all(s.status == UniversalStorageStatus.BOUGHT for s in storages)

            # баланс уменьшен
            db_user = await session.get(Users, user.user_id)
            assert db_user.balance < user.balance

        # файлы реально переехали
        for p in products:
            final = create_path_universal_storage(
                status=UniversalStorageStatus.BOUGHT,
                uuid=p.universal_storage.storage_uuid,
            )
            original = create_path_universal_storage(
                status=UniversalStorageStatus.FOR_SALE,
                uuid=p.universal_storage.storage_uuid,
            )

            assert os.path.exists(final), f"Файл не найден в bought: {final}"
            assert not os.path.exists(original), f"Исходная директория не удалена: {original}"


    @pytest.mark.asyncio
    async def test_purchase_universal_fail_verify_different(
        self,
        patch_fake_aiogram,
        monkeypatch,
        create_new_user,
        create_category,
        create_product_universal,
    ):
        """
        Если verify_reserved_universal_different вернул False:
        - PurchaseRequests.status == failed
        - BalanceHolder.status == released
        - UniversalStorage.status возвращён в for_sale
        - баланс пользователя восстановлен
        """
        from src.services.filesystem.media_paths import create_path_universal_storage
        from src.services.database.categories.actions.purchases.main_purchase import purchase_universal
        from src.services.database.categories.actions.purchases.universal import verify as verify_mod

        user = await create_new_user(balance=5_000)
        category = await create_category(price=500)
        category_id = category.category_id
        quantity = 2

        products = []
        for _ in range(quantity):
            _, product = await create_product_universal(category_id=category_id)
            products.append(product)

        async def always_false(products, purchase_request_id):
            return False

        monkeypatch.setattr(
            verify_mod,
            "check_valid_universal_product",
            always_false,
        )

        await purchase_universal(
            user_id=user.user_id,
            category_id=category_id,
            quantity_products=quantity,
            language="ru",
            promo_code_id=None,
        )

        async with get_db() as session:
            q = await session.execute(
                select(PurchaseRequests)
                .where(PurchaseRequests.user_id == user.user_id)
                .order_by(PurchaseRequests.purchase_request_id.desc())
            )
            pr = q.scalars().first()
            assert pr is not None
            assert pr.status == "failed"

            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().first()
            assert bh is not None
            assert bh.status == "released"

            storage_ids = [p.universal_storage_id for p in products]
            q = await session.execute(
                select(UniversalStorage).where(
                    UniversalStorage.universal_storage_id.in_(storage_ids)
                )
            )
            storages = q.scalars().all()
            assert all(s.status == UniversalStorageStatus.FOR_SALE for s in storages)

            db_user = await session.get(Users, user.user_id)
            assert db_user.balance == user.balance

        for p in products:
            bought = create_path_universal_storage(
                status=UniversalStorageStatus.BOUGHT,
                uuid=p.universal_storage.storage_uuid,
            )
            sale = create_path_universal_storage(
                status=UniversalStorageStatus.FOR_SALE,
                uuid=p.universal_storage.storage_uuid,
            )

            assert not os.path.exists(bought)
            assert os.path.exists(sale)


class TestOnePurchase:
    @pytest.mark.asyncio
    async def test_purchase_universal_success_one(
        self,
        patch_fake_aiogram,
        monkeypatch,
        create_new_user,
        create_category,
        create_product_universal,
    ):
        """
        Интеграционный тест:
        - покупка universal (one) проходит успешно;
        - создаются SoldUniversal / Purchases;
        - PurchaseRequests.status -> completed
        - BalanceHolder.status -> used
        - UniversalStorage.status -> bought
        - файл реально перемещён в bought
        """
        from src.services.filesystem.media_paths import create_path_universal_storage
        from src.services.database.categories.actions.purchases.main_purchase import purchase_universal

        user = await create_new_user(balance=5_000)
        category = await create_category(
            price=500,
            product_type=ProductType.UNIVERSAL,
            allow_multiple_purchase=True,
        )
        category_id = category.category_id

        storage, product = await create_product_universal(category_id=category_id)

        result = await purchase_universal(
            user_id=user.user_id,
            category_id=category_id,
            quantity_products=1,
            language="ru",
            promo_code_id=None,
        )

        assert result is True

        async with get_db() as session:
            # PurchaseRequest
            q = await session.execute(
                select(PurchaseRequests)
                .where(PurchaseRequests.user_id == user.user_id)
                .order_by(PurchaseRequests.purchase_request_id.desc())
            )
            pr = q.scalars().first()
            assert pr is not None
            assert pr.status == "completed"

            # BalanceHolder
            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().first()
            assert bh is not None
            assert bh.status == "used"

            # SoldUniversal
            q = await session.execute(
                select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id)
            )
            sold = q.scalars().all()
            assert len(sold) == 1

            # Purchases
            q = await session.execute(
                select(Purchases).where(Purchases.user_id == user.user_id)
            )
            purchases = q.scalars().all()
            assert len(purchases) >= 1

            # У товара который стоит на продаже не должен поменяться статус
            storage_db = await session.get(
                UniversalStorage,
                product.universal_storage_id,
            )
            assert storage_db.status == UniversalStorageStatus.FOR_SALE

            q = await session.execute(
                select(UniversalStorage)
                .where(UniversalStorage.universal_storage_id != product.universal_storage_id)
            )
            purchases_storage: List[UniversalStorage] = q.scalars().all()
            assert purchases_storage

            storage_paths_files: List[str] = []
            for storage in purchases_storage:
                assert storage.status == UniversalStorageStatus.BOUGHT
                storage_paths_files.append(
                        create_path_universal_storage(
                            status=storage.status,
                            uuid=storage.storage_uuid,
                    )
                )

            # баланс уменьшен
            db_user = await session.get(Users, user.user_id)
            assert db_user.balance < user.balance

        # файл товара который стоит на продаже не должен переместиться
        final_path = create_path_universal_storage(
            status=UniversalStorageStatus.FOR_SALE,
            uuid=product.universal_storage.storage_uuid,
        )

        assert os.path.exists(final_path)

        for new_storage in storage_paths_files:
            assert os.path.exists(new_storage)


    @pytest.mark.asyncio
    async def test_purchase_universal_fail_verify_one(
        self,
        patch_fake_aiogram,
        monkeypatch,
        create_new_user,
        create_category,
        create_product_universal,
    ):
        """
        Если verify_reserved_universal_one вернул False:
        - PurchaseRequests.status == failed
        - BalanceHolder.status == released
        - UniversalStorage.status -> for_sale
        - баланс пользователя восстановлен
        """
        from src.services.filesystem.media_paths import create_path_universal_storage
        from src.services.database.categories.actions.purchases.main_purchase import purchase_universal

        user = await create_new_user(balance=5_000)
        category = await create_category(
            price=500,
            product_type=ProductType.UNIVERSAL,
            allow_multiple_purchase=True,
        )
        category_id = category.category_id

        _, product = await create_product_universal(category_id=category_id, encrypted_tg_file_id_nonce="fake_nonce")

        await purchase_universal(
            user_id=user.user_id,
            category_id=category_id,
            quantity_products=1,
            language="ru",
            promo_code_id=None,
        )

        async with get_db() as session:
            q = await session.execute(
                select(PurchaseRequests)
                .where(PurchaseRequests.user_id == user.user_id)
                .order_by(PurchaseRequests.purchase_request_id.desc())
            )
            pr = q.scalars().first()
            assert pr is not None
            assert pr.status == "failed"

            q = await session.execute(
                select(BalanceHolder).where(
                    BalanceHolder.purchase_request_id == pr.purchase_request_id
                )
            )
            bh = q.scalars().first()
            assert bh is not None
            assert bh.status == "released"

            storage_db = await session.get(
                UniversalStorage,
                product.universal_storage_id,
            )
            assert storage_db.status == UniversalStorageStatus.DELETED

            db_user = await session.get(Users, user.user_id)
            assert db_user.balance == user.balance

        bought_path = create_path_universal_storage(
            status=UniversalStorageStatus.BOUGHT,
            uuid=product.universal_storage.storage_uuid,
        )
        sale_path = create_path_universal_storage(
            status=UniversalStorageStatus.FOR_SALE,
            uuid=product.universal_storage.storage_uuid,
        )
        deleted_path = create_path_universal_storage(
            status=UniversalStorageStatus.DELETED,
            uuid=product.universal_storage.storage_uuid,
        )
        assert not os.path.exists(bought_path)
        assert not os.path.exists(sale_path)
        assert os.path.exists(deleted_path)
