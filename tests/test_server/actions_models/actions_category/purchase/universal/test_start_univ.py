import orjson
import pytest
from sqlalchemy import select

from src.exceptions.business import NotEnoughProducts
from src.exceptions.domain import UniversalProductNotFound
from src.services.database.categories.models import (
    PurchaseRequests
)
from src.services.database.categories.models.product_universal import (
    UniversalStorage,
    UniversalStorageStatus,
    PurchaseRequestUniversal,
)
from src.services.database.core.database import get_db
from src.services.database.users.models import Users, BalanceHolder
from src.services.redis.core_redis import get_redis
from tests.helpers.helper_functions import comparison_models


class TestStartPurchaseUniversalDifferent:
    """
    allow_multiple_purchase = False
    """

    @pytest.mark.asyncio
    async def test_start_purchase_universal_success_different(
        self,
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_category,
        create_translate_category,
        create_universal_storage,
        create_product_universal,
    ):
        """
        Успешная покупка универсальных товаров (разные экземпляры):
        - создаётся PurchaseRequests (status=processing)
        - создаются PurchaseRequestUniversal (по количеству)
        - создаётся BalanceHolder
        - списывается баланс пользователя
        - UniversalStorage.status -> RESERVED
        - корректный StartPurchaseUniversal
        """
        from src.services.database.categories.actions.purchases.universal.start import start_purchase_universal

        user = await create_new_user(balance=10_000)
        category = await create_category(
            price=500,
            allow_multiple_purchase=False,
        )

        quantity = 3

        storages = []
        products_full = []

        for _ in range(quantity):
            storage, _ = await create_universal_storage()
            _, full = await create_product_universal(
                universal_storage_id=storage.universal_storage_id,
                category_id=category.category_id,
            )
            storages.append(storage)
            products_full.append(full)

        async with get_db() as session:
            db_user = await session.get(Users, user.user_id)
            balance_before = db_user.balance

        result = await start_purchase_universal(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=quantity,
            promo_code_id=None,
            language="ru",
        )

        # return object
        assert result.purchase_request_id is not None
        assert result.category_id == category.category_id
        assert len(result.full_reserved_products) == quantity
        assert result.user_balance_before == balance_before
        assert result.user_balance_after == balance_before - result.total_amount

        # DB checks
        async with get_db() as session:
            pr = await session.get(PurchaseRequests, result.purchase_request_id)
            assert pr is not None
            assert pr.quantity == quantity
            assert pr.status == "processing"

            q = await session.execute(
                select(PurchaseRequestUniversal)
                .where(PurchaseRequestUniversal.purchase_request_id == pr.purchase_request_id)
            )
            pr_universal = q.scalars().all()
            assert len(pr_universal) == quantity

            q = await session.execute(
                select(BalanceHolder)
                .where(BalanceHolder.purchase_request_id == pr.purchase_request_id)
            )
            holder = q.scalars().first()
            assert holder is not None
            assert holder.amount == result.total_amount

            storage_ids = [p.universal_storage_id for p in pr_universal]
            q = await session.execute(
                select(UniversalStorage)
                .where(UniversalStorage.universal_storage_id.in_(storage_ids))
            )
            storages_db = q.scalars().all()
            assert all(s.status == UniversalStorageStatus.RESERVED for s in storages_db)

            user_after = await session.get(Users, user.user_id)
            assert user_after.balance == balance_before - result.total_amount

        # Redis checks
        async with get_redis() as redis:
            user_dict = orjson.loads(await redis.get(f"user:{user.user_id}"))
            assert comparison_models(user_after.to_dict(), user_dict)

            for product in result.full_reserved_products:
                redis_product = await redis.get(f"product_universal:{product.product_universal_id}")
                assert redis_product is not None


    @pytest.mark.asyncio
    async def test_start_purchase_universal_not_enough_products(
        self,
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_category,
        create_translate_category,
        create_universal_storage,
        create_product_universal,
    ):
        """
        Недостаточно товаров → NotEnoughProducts
        """
        from src.services.database.categories.actions.purchases.universal.start import start_purchase_universal

        user = await create_new_user(balance=10_000)
        category = await create_category(
            allow_multiple_purchase=False,
            price=100,
        )

        storage, _ = await create_universal_storage()
        await create_product_universal(
            universal_storage_id=storage.universal_storage_id,
            category_id=category.category_id,
        )

        with pytest.raises(NotEnoughProducts):
            await start_purchase_universal(
                user_id=user.user_id,
                category_id=category.category_id,
                quantity_products=5,
                promo_code_id=None,
                language="ru",
            )


class TestStartPurchaseUniversalOne:
    """
    allow_multiple_purchase = True
    """

    @pytest.mark.asyncio
    async def test_start_purchase_universal_one_success(
        self,
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_category,
        create_translate_category,
        create_universal_storage,
        create_product_universal,
    ):
        """
        allow_multiple_purchase=True:
        - НЕ резервируются UniversalStorage
        - покупка одного и того же товара
        - корректный StartPurchaseUniversalOne
        """
        from src.services.database.categories.actions.purchases.universal.start import start_purchase_universal

        user = await create_new_user(balance=10_000)
        category = await create_category(
            price=1000,
            allow_multiple_purchase=True,
        )

        storage, _ = await create_universal_storage()
        _, product_full = await create_product_universal(
            universal_storage_id=storage.universal_storage_id,
            category_id=category.category_id,
        )

        async with get_db() as session:
            balance_before = (await session.get(Users, user.user_id)).balance

        quantity = 2

        result = await start_purchase_universal(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=quantity,
            promo_code_id=None,
            language="ru",
        )

        assert result.purchase_request_id is not None
        assert result.full_product.product_universal_id == product_full.product_universal_id
        assert result.quantity_products == quantity
        assert result.user_balance_before == balance_before
        assert result.user_balance_after == balance_before - result.total_amount

        async with get_db() as session:
            storage_db = await session.get(
                UniversalStorage,
                storage.universal_storage_id,
            )
            # статус НЕ должен измениться
            assert storage_db.status == UniversalStorageStatus.FOR_SALE


    @pytest.mark.asyncio
    async def test_start_purchase_universal_one_product_not_found(
        self,
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_category,
    ):
        """
        Если get_product_universal_by_category_id вернул пусто → UniversalProductNotFound
        """
        from src.services.database.categories.actions.purchases.universal.start import start_purchase_universal

        user = await create_new_user(balance=10_000)
        category = await create_category(
            allow_multiple_purchase=True,
        )

        with pytest.raises(UniversalProductNotFound):
            await start_purchase_universal(
                user_id=user.user_id,
                category_id=category.category_id,
                quantity_products=1,
                promo_code_id=None,
                language="ru",
            )
