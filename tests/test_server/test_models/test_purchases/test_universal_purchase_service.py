import pytest
from sqlalchemy import select

import src.application.models.purchases.universal.universal_purchase_service as universal_purchase_module
from src.database.models.categories import ProductType, StorageStatus
from src.database.models.categories.main_category_and_product import PurchaseRequests, Purchases
from src.database.models.categories.product_universal import UniversalStorage, SoldUniversal
from src.database.models.users import BalanceHolder
from src.database.models.users.models_users import Users
from tests.helpers.fixtures.helper_fixture import (
    container_fix,
    create_category,
    create_new_user,
    create_product_universal,
)


@pytest.mark.asyncio
async def test_universal_purchase_service_start_and_finalize_different(
    container_fix,
    create_category,
    create_new_user,
    create_product_universal,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=3_000)
    category = await create_category(
        is_product_storage=True,
        product_type=ProductType.UNIVERSAL,
        reuse_product=False,
        price=150,
        cost_price=60,
    )

    original_check_valid = container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product

    async def fake_check_valid(*args, **kwargs):
        return True

    container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = fake_check_valid
    products = []
    try:
        for _ in range(3):
            _, full = await create_product_universal(category_id=category.category_id, language="ru")
            products.append(full)

        start_result = await container_fix.universal_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=2,
            promo_code_id=None,
            language="ru",
        )
        assert len(start_result.full_reserved_products) == 2

        finalized = await container_fix.universal_purchase_service.finalize_purchase_different(
            user_id=user.user_id,
            data=start_result,
        )
        assert finalized is True
    finally:
        container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = original_check_valid

    request_db = await container_fix.session_db.get(PurchaseRequests, start_result.purchase_request_id)
    assert request_db.status == "completed"

    holder_db = await container_fix.session_db.execute(
        select(BalanceHolder).where(BalanceHolder.purchase_request_id == start_result.purchase_request_id)
    )
    assert holder_db.scalar_one().status == "used"

    sold_db = await container_fix.session_db.execute(
        select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id)
    )
    assert len(sold_db.scalars().all()) == 2

    purchase_db = await container_fix.session_db.execute(select(Purchases).where(Purchases.user_id == user.user_id))
    assert len(purchase_db.scalars().all()) == 2

    storage_db = await container_fix.session_db.execute(
        select(UniversalStorage).where(
            UniversalStorage.universal_storage_id.in_([p.universal_storage_id for p in products])
        )
    )
    storages = storage_db.scalars().all()
    assert any(item.status == StorageStatus.BOUGHT for item in storages)
    assert any(item.status == StorageStatus.FOR_SALE for item in storages)

@pytest.mark.asyncio
async def test_universal_purchase_service_start_and_finalize_one(
    container_fix,
    create_category,
    create_new_user,
    create_product_universal,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=3_000)
    category = await create_category(
        is_product_storage=True,
        product_type=ProductType.UNIVERSAL,
        reuse_product=True,
        price=120,
        cost_price=50,
    )

    _, full = await create_product_universal(category_id=category.category_id, language="ru")

    original_get_full = container_fix.universal_purchase_service.product_repo.get_full_by_category

    async def fake_get_full_by_category(*args, **kwargs):
        return [full]

    container_fix.universal_purchase_service.product_repo.get_full_by_category = fake_get_full_by_category
    try:
        start_result = await container_fix.universal_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=1,
            promo_code_id=None,
            language="ru",
        )
        assert start_result.full_product.product_universal_id == full.product_universal_id

        finalized = await container_fix.universal_purchase_service.finalize_purchase_one(
            user_id=user.user_id,
            data=start_result,
        )
        assert finalized is True
    finally:
        container_fix.universal_purchase_service.product_repo.get_full_by_category = original_get_full

    request_db = await container_fix.session_db.get(PurchaseRequests, start_result.purchase_request_id)
    assert request_db.status == "completed"

    holder_db = await container_fix.session_db.execute(
        select(BalanceHolder).where(BalanceHolder.purchase_request_id == start_result.purchase_request_id)
    )
    assert holder_db.scalar_one().status == "used"

    sold_db = await container_fix.session_db.execute(
        select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id)
    )
    assert len(sold_db.scalars().all()) == 1

    storage_db = await container_fix.session_db.execute(
        select(UniversalStorage).where(UniversalStorage.universal_storage_id == full.universal_storage_id)
    )
    storages = storage_db.scalars().all()
    assert any(item.status == StorageStatus.FOR_SALE for item in storages)


@pytest.mark.asyncio
async def test_universal_purchase_service_finalize_failure_uses_real_cancel_path(
    container_fix,
    create_category,
    create_new_user,
    create_product_universal,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=3_000)
    category = await create_category(
        is_product_storage=True,
        product_type=ProductType.UNIVERSAL,
        reuse_product=False,
        price=150,
        cost_price=60,
    )

    original_check_valid = container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product

    async def fake_check_valid(*args, **kwargs):
        return True

    container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = fake_check_valid
    try:
        for _ in range(2):
            await create_product_universal(category_id=category.category_id, language="ru")

        start_result = await container_fix.universal_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=2,
            promo_code_id=None,
            language="ru",
        )
    finally:
        container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = original_check_valid

    original_move_file = universal_purchase_module.move_file

    async def fake_move_file(*args, **kwargs):
        return False

    universal_purchase_module.move_file = fake_move_file
    try:
        finalized = await container_fix.universal_purchase_service.finalize_purchase_different(
            user_id=user.user_id,
            data=start_result,
        )
        assert finalized is False
    finally:
        universal_purchase_module.move_file = original_move_file

    request_db = await container_fix.session_db.get(PurchaseRequests, start_result.purchase_request_id)
    assert request_db.status == "failed"

    holder_db = await container_fix.session_db.execute(
        select(BalanceHolder).where(BalanceHolder.purchase_request_id == start_result.purchase_request_id)
    )
    assert holder_db.scalar_one().status == "released"

    user_db = await container_fix.session_db.get(Users, user.user_id)
    assert user_db.balance == user.balance


@pytest.mark.asyncio
async def test_universal_purchase_service_verify_reserved_paths_real_candidates(
    container_fix,
    create_category,
    create_new_user,
    create_product_universal,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=2_000)
    category = await create_category(
        container_fix,
        is_product_storage=True,
        product_type=ProductType.UNIVERSAL,
        reuse_product=False,
    )

    spare_product, spare_full = await create_product_universal(category_id=category.category_id, language="ru")
    reserved_one, full_one = await create_product_universal(category_id=category.category_id, language="ru")
    reserved_two, full_two = await create_product_universal(category_id=category.category_id, language="ru")

    original_check_valid = container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product

    async def fake_check_valid(product, status):
        return getattr(product.universal_storage, "encrypted_key", "") != "broken"

    container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = fake_check_valid
    try:
        start_result = await container_fix.universal_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=2,
            promo_code_id=None,
            language="ru",
        )

        start_result.full_reserved_products[0].universal_storage.encrypted_key = "broken"

        verified = await container_fix.universal_purchase_service.verify_reserved_universal_different(
            start_result.full_reserved_products,
            start_result.purchase_request_id,
        )
        assert verified is not False
        assert len(verified) == 2
        assert any(item.product_universal_id == spare_full.product_universal_id for item in verified)

        broken_storage = await container_fix.session_db.get(
            UniversalStorage,
            start_result.full_reserved_products[0].universal_storage_id,
        )
        assert broken_storage.status == StorageStatus.DELETED
    finally:
        container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = original_check_valid


@pytest.mark.asyncio
async def test_universal_purchase_service_verify_reserved_one_and_cancel(
    container_fix,
    create_category,
    create_product_universal,
):
    await container_fix.session_db.rollback()
    category = await create_category(
        container_fix,
        is_product_storage=True,
        product_type=ProductType.UNIVERSAL,
        reuse_product=True,
    )

    _, full = await create_product_universal(category_id=category.category_id, language="ru")
    full.universal_storage.encrypted_key = "broken"

    assert await container_fix.universal_purchase_service.verify_reserved_universal_one(full) is False

    storage = await container_fix.session_db.get(UniversalStorage, full.universal_storage_id)
    assert storage.status == StorageStatus.DELETED


@pytest.mark.asyncio
async def test_universal_purchase_service_cancel_one_restores_state(
    container_fix,
    create_category,
    create_new_user,
    create_product_universal,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=1_000)
    category = await create_category(
        container_fix,
        is_product_storage=True,
        product_type=ProductType.UNIVERSAL,
        reuse_product=True,
    )

    _, full = await create_product_universal(category_id=category.category_id, language="ru")

    original_get_full = container_fix.universal_purchase_service.product_repo.get_full_by_category

    async def fake_get_full_by_category(*args, **kwargs):
        return [full]

    container_fix.universal_purchase_service.product_repo.get_full_by_category = fake_get_full_by_category
    try:
        start_result = await container_fix.universal_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=1,
            promo_code_id=None,
            language="ru",
        )
        product = start_result.full_product
    finally:
        container_fix.universal_purchase_service.product_repo.get_full_by_category = original_get_full

    temp_file = container_fix.config.paths.temp_dir / "created_storage.part"
    temp_file.write_text("temp", encoding="utf-8")

    await container_fix.universal_purchase_service.cancel_purchase_one(
        user_id=user.user_id,
        category_id=category.category_id,
        paths_created_storage=[str(temp_file)],
        sold_universal_ids=[],
        storage_universal_ids=[],
        purchase_ids=[],
        total_amount=start_result.total_amount,
        purchase_request_id=start_result.purchase_request_id,
        product_universal=product,
    )

    assert not temp_file.exists()

    user_db = await container_fix.session_db.get(Users, user.user_id)
    assert user_db.balance == user.balance

    storage_db = await container_fix.session_db.get(UniversalStorage, product.universal_storage_id)
    assert storage_db.status == StorageStatus.FOR_SALE
