import pytest
from sqlalchemy import select

from src.services.database.core.database import get_db
from src.services.database.categories.models.product_universal import (
    UniversalStorage,
    UniversalStorageStatus,
)



class TestVerifyReservedUniversalOne:
    @pytest.mark.asyncio
    async def test_verify_reserved_universal_one_valid(
        self,
        patch_fake_aiogram,
        create_category,
        create_universal_storage,
        create_product_universal,
        monkeypatch,
    ):
        """
        allow_multiple_purchase=True
        Продукт валиден → возвращается True, ничего не удаляется.
        """
        from src.services.database.categories.actions.purchases.universal.verify import verify_reserved_universal_one

        category = await create_category(allow_multiple_purchase=True)
        _, product_full = await create_product_universal(category_id=category.category_id)

        result = await verify_reserved_universal_one(product_full)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_reserved_universal_one_invalid(
        self,
        patch_fake_aiogram,
        create_category,
        create_product_universal,
        monkeypatch,
    ):
        """
        allow_multiple_purchase=True
        Продукт невалиден → удаляется, возвращается False.
        """
        from src.services.database.categories.actions.purchases.universal import verify
        from src.services.database.categories.actions.purchases.universal.verify import (
            verify_reserved_universal_one,
        )

        category = await create_category(allow_multiple_purchase=True)
        _, product_full = await create_product_universal(category_id=category.category_id)

        async def always_invalid(*a, **kw):
            return False

        monkeypatch.setattr(verify,"check_valid_universal_product", always_invalid)

        result = await verify_reserved_universal_one(product_full)
        assert result is False

        async with get_db() as session:
            storage = await session.get(
                UniversalStorage,
                product_full.universal_storage.universal_storage_id,
            )
            assert storage.status == UniversalStorageStatus.DELETED
            assert storage.is_active is False


class TestVerifyReservedUniversalDifferent:
    @pytest.mark.asyncio
    async def test_all_valid(
        self,
        patch_fake_aiogram,
        create_category,
        create_product_universal,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Все зарезервированные универсальные продукты валидны → возвращается тот же список.
        """
        from src.services.database.categories.actions.purchases.universal.verify import (
            verify_reserved_universal_different,
        )

        category = await create_category(allow_multiple_purchase=False)

        products = []
        for _ in range(3):
            _, full = await create_product_universal(category_id=category.category_id)
            products.append(full)

        pr = await create_purchase_request(quantity=3, total_amount=0)
        pr_id = pr.purchase_request_id

        result = await verify_reserved_universal_different(products, pr_id)

        assert isinstance(result, list)
        assert len(result) == 3
        returned_ids = {p.product_universal_id for p in result}
        assert returned_ids == {p.product_universal_id for p in products}

    @pytest.mark.asyncio
    async def test_one_invalid_replaced(
        self,
        patch_fake_aiogram,
        create_category,
        create_product_universal,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Один продукт невалиден, но найден валидный кандидат → замена успешна.
        """
        from src.services.database.categories.actions.purchases.universal import verify
        from src.services.database.categories.actions.purchases.universal.verify import (
            verify_reserved_universal_different,
        )

        category = await create_category(allow_multiple_purchase=False)

        # плохой
        _, bad = await create_product_universal(category_id=category.category_id)

        # кандидат
        _, candidate = await create_product_universal(category_id=category.category_id)

        pr = await create_purchase_request(quantity=1, total_amount=0)
        pr_id = pr.purchase_request_id

        async def validity(prod, *a, **kw):
            return prod.product_universal_id != bad.product_universal_id

        monkeypatch.setattr(verify,"check_valid_universal_product", validity)

        result = await verify_reserved_universal_different([bad], pr_id)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].product_universal_id == candidate.product_universal_id

        async with get_db() as session:
            bad_storage = await session.get(
                UniversalStorage,
                bad.universal_storage.universal_storage_id,
            )
            assert bad_storage.status == UniversalStorageStatus.DELETED

    @pytest.mark.asyncio
    async def test_all_invalid_no_candidates(
        self,
        patch_fake_aiogram,
        create_category,
        create_product_universal,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Все невалидны и нет кандидатов → возвращается False, все удалены.
        """
        from src.services.database.categories.actions.purchases.universal import verify
        from src.services.database.categories.actions.purchases.universal.verify import (
            verify_reserved_universal_different,
        )

        category = await create_category(allow_multiple_purchase=False)

        products = []
        for _ in range(2):
            _, full = await create_product_universal(category_id=category.category_id)
            products.append(full)

        pr = await create_purchase_request(quantity=2, total_amount=0)
        pr_id = pr.purchase_request_id

        async def always_invalid(*a, **kw):
            return False

        monkeypatch.setattr(verify,"check_valid_universal_product", always_invalid)

        result = await verify_reserved_universal_different(products, pr_id)
        assert result is False

        async with get_db() as session:
            ids = [p.universal_storage.universal_storage_id for p in products]
            q = await session.execute(
                select(UniversalStorage).where(
                    UniversalStorage.universal_storage_id.in_(ids)
                )
            )
            storages = q.scalars().all()
            assert all(s.status == UniversalStorageStatus.DELETED for s in storages)

    @pytest.mark.asyncio
    async def test_partial_invalid_not_enough_replacements(
        self,
        patch_fake_aiogram,
        create_category,
        create_product_universal,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Часть валидна, часть нет, кандидатов недостаточно → False.
        """
        from src.services.database.categories.actions.purchases.universal import verify
        from src.services.database.categories.actions.purchases.universal.verify import (
            verify_reserved_universal_different,
        )

        category = await create_category(allow_multiple_purchase=False)

        _, valid = await create_product_universal(category_id=category.category_id, status=UniversalStorageStatus.RESERVED)
        _, bad = await create_product_universal(category_id=category.category_id, status=UniversalStorageStatus.RESERVED)

        pr = await create_purchase_request(quantity=2, total_amount=0)
        pr_id = pr.purchase_request_id

        async def validity(prod, *a, **kw):
            return prod.product_universal_id == valid.product_universal_id

        monkeypatch.setattr(verify,"check_valid_universal_product", validity)

        result = await verify_reserved_universal_different([valid, bad], pr_id)
        assert result is False
