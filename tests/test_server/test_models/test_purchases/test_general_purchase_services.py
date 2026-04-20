import shutil

import pytest
from sqlalchemy import select

from src.database.models.categories import AccountServiceType, ProductType, StorageStatus
from src.database.models.categories.main_category_and_product import PurchaseRequests, Purchases
from src.database.models.categories.product_account import AccountStorage
from src.database.models.categories.product_account import SoldAccounts
from src.database.models.categories.product_universal import SoldUniversal
from src.database.models.users.models_users import Users
from src.exceptions import CategoryNotFound, NotEnoughMoney
from src.exceptions.business import InvalidQuantityProducts
from tests.helpers.fixtures.helper_fixture import (
    container_fix,
    create_category,
    create_new_user,
    create_promo_code,
    create_purchase_request,
)


@pytest.mark.asyncio
async def test_purchase_service_rejects_non_positive_quantity(container_fix):
    with pytest.raises(InvalidQuantityProducts):
        await container_fix.purchase_service.purchase(
            user_id=1,
            category_id=1,
            quantity_products=0,
            promo_code_id=None,
            product_type=ProductType.ACCOUNT,
            language="ru",
        )


@pytest.mark.asyncio
async def test_purchase_request_service_handles_request_and_balance(container_fix, create_new_user):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=500)

    request = await container_fix.purchase_request_service.create_request(
        user_id=user.user_id,
        promo_code_id=None,
        quantity=2,
        total_amount=120,
    )
    assert request.user_id == user.user_id
    assert request.quantity == 2
    assert request.total_amount == 120

    held_user = await container_fix.purchase_request_service.hold_funds(
        user_id=user.user_id,
        purchase_request_id=request.purchase_request_id,
        amount=120,
    )
    assert held_user.balance == user.balance - 120

    released_user = await container_fix.purchase_request_service.release_funds(
        user_id=user.user_id,
        amount=120,
    )
    assert released_user.balance == user.balance

    await container_fix.purchase_request_service.mark_request_status(request.purchase_request_id, "completed")
    await container_fix.purchase_request_service.mark_balance_holder_status(request.purchase_request_id, "used")
    await container_fix.session_db.commit()

    request_db = await container_fix.purchase_request_service.purchase_request_repo.get_by_id(
        request.purchase_request_id
    )
    assert request_db.status == "completed"

    holder_db = await container_fix.purchase_request_service.balance_holder_repo.get_by_request_id(
        request.purchase_request_id
    )
    assert holder_db.status == "used"


@pytest.mark.asyncio
async def test_purchase_validation_service_checks_prices_and_errors(
    container_fix,
    create_category,
    create_new_user,
    create_promo_code,
):
    await container_fix.session_db.rollback()
    category = await create_category(
        is_product_storage=True,
        price=100,
        cost_price=60,
    )
    user = await create_new_user(balance=500)

    checked = await container_fix.purchase_validation_service.check_category_and_money(
        user_id=user.user_id,
        category_id=category.category_id,
        quantity_products=2,
        promo_code_id=None,
    )
    assert checked.category.category_id == category.category_id
    assert checked.final_total == 200
    assert checked.user_balance_before == user.balance

    promo = await create_promo_code(amount=50)
    checked_with_promo = await container_fix.purchase_validation_service.check_category_and_money(
        user_id=user.user_id,
        category_id=category.category_id,
        quantity_products=2,
        promo_code_id=promo.promo_code_id,
    )
    assert checked_with_promo.final_total == 150

    low_balance_user = await create_new_user(balance=10)
    with pytest.raises(NotEnoughMoney):
        await container_fix.purchase_validation_service.check_category_and_money(
            user_id=low_balance_user.user_id,
            category_id=category.category_id,
            quantity_products=1,
            promo_code_id=None,
        )

    with pytest.raises(CategoryNotFound):
        await container_fix.purchase_validation_service.check_category_and_money(
            user_id=user.user_id,
            category_id=999999,
            quantity_products=1,
            promo_code_id=None,
        )


@pytest.mark.asyncio
async def test_purchase_cancel_service_marks_failed_and_restores_files(
    container_fix,
    create_new_user,
    create_purchase_request,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=250)
    purchase_request = await create_purchase_request(
        user_id=user.user_id,
        total_amount=120,
        quantity=2,
    )

    await container_fix.purchase_request_service.hold_funds(
        user_id=user.user_id,
        purchase_request_id=purchase_request.purchase_request_id,
        amount=120,
    )
    await container_fix.purchase_cancel_service.mark_failed(purchase_request.purchase_request_id)
    await container_fix.session_db.commit()

    failed_request = await container_fix.purchase_request_service.purchase_request_repo.get_by_id(
        purchase_request.purchase_request_id
    )
    assert failed_request.status == "failed"

    balance_holder = await container_fix.purchase_request_service.balance_holder_repo.get_by_request_id(
        purchase_request.purchase_request_id
    )
    assert balance_holder.status == "released"

    work_dir = container_fix.config.paths.temp_dir / "purchase_cancel"
    work_dir.mkdir(parents=True, exist_ok=True)
    orig = work_dir / "orig" / "sample.txt"
    temp = work_dir / "temp" / "sample.txt"
    final = work_dir / "final" / "sample.txt"
    temp.parent.mkdir(parents=True, exist_ok=True)
    final.parent.mkdir(parents=True, exist_ok=True)
    temp.write_text("temp", encoding="utf-8")
    final.write_text("final", encoding="utf-8")

    try:
        await container_fix.purchase_cancel_service.return_files([(str(orig), str(temp), str(final))])
        assert orig.exists()
        assert not temp.exists()
        assert not final.exists()
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_purchase_service_purchase_accounts_end_to_end(
    container_fix,
    create_category,
    create_new_user,
    create_product_account,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=2_000)
    category = await create_category(
        is_product_storage=True,
        price=100,
        cost_price=40,
        type_account_service=AccountServiceType.OTHER,
    )

    product_rows = []
    for phone_suffix in ("01", "02"):
        product, _ = await create_product_account(
            category_id=category.category_id,
            type_account_service=AccountServiceType.OTHER,
            phone_number=f"+79991120{phone_suffix}",
        )
        product_rows.append(product)

    original_check_valid = container_fix.account_purchase_service.validate_other_account.check_valid

    async def fake_check_valid(*args, **kwargs):
        return True

    container_fix.account_purchase_service.validate_other_account.check_valid = fake_check_valid
    try:
        result = await container_fix.purchase_service.purchase_accounts(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_accounts=2,
            promo_code_id=None,
        )
    finally:
        container_fix.account_purchase_service.validate_other_account.check_valid = original_check_valid

    assert result is True

    user_db = await container_fix.session_db.get(Users, user.user_id)
    assert user_db.balance == user.balance - 200

    request_db = await container_fix.session_db.execute(
        select(PurchaseRequests).where(PurchaseRequests.user_id == user.user_id)
    )
    assert request_db.scalar_one().status == "completed"

    sold_db = await container_fix.session_db.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
    assert len(sold_db.scalars().all()) == 2

    purchase_db = await container_fix.session_db.execute(select(Purchases).where(Purchases.user_id == user.user_id))
    assert len(purchase_db.scalars().all()) == 2

    storage_db = await container_fix.session_db.execute(
        select(AccountStorage).where(AccountStorage.account_storage_id.in_([p.account_storage_id for p in product_rows]))
    )
    assert all(item.status == StorageStatus.BOUGHT for item in storage_db.scalars().all())


@pytest.mark.asyncio
async def test_purchase_service_purchase_universal_end_to_end(
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

    for _ in range(2):
        await create_product_universal(category_id=category.category_id, language="ru")

    original_check_valid = container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product

    async def fake_check_valid(*args, **kwargs):
        return True

    container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = fake_check_valid
    try:
        result = await container_fix.purchase_service.purchase_universal(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=2,
            language="ru",
            promo_code_id=None,
        )
    finally:
        container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = original_check_valid

    assert result is True

    user_db = await container_fix.session_db.get(Users, user.user_id)
    assert user_db.balance == user.balance - 300

    request_db = await container_fix.session_db.execute(
        select(PurchaseRequests).where(PurchaseRequests.user_id == user.user_id)
    )
    assert request_db.scalar_one().status == "completed"

    sold_db = await container_fix.session_db.execute(select(SoldUniversal).where(SoldUniversal.owner_id == user.user_id))
    assert len(sold_db.scalars().all()) == 2

    purchase_db = await container_fix.session_db.execute(select(Purchases).where(Purchases.user_id == user.user_id))
    assert len(purchase_db.scalars().all()) == 2


@pytest.mark.asyncio
async def test_purchase_service_purchase_routes_to_real_services(
    container_fix,
    create_category,
    create_new_user,
    create_product_account,
    create_product_universal,
):
    await container_fix.session_db.rollback()

    account_user = await create_new_user(balance=2_000)
    account_category = await create_category(
        is_product_storage=True,
        price=100,
        cost_price=40,
        type_account_service=AccountServiceType.OTHER,
    )
    for phone_suffix in ("11", "12"):
        await create_product_account(
            category_id=account_category.category_id,
            type_account_service=AccountServiceType.OTHER,
            phone_number=f"+79991130{phone_suffix}",
        )

    universal_user = await create_new_user(balance=3_000, user_name="universal_user")
    universal_category = await create_category(
        is_product_storage=True,
        product_type=ProductType.UNIVERSAL,
        reuse_product=False,
        price=150,
        cost_price=60,
    )
    for _ in range(2):
        await create_product_universal(category_id=universal_category.category_id, language="ru")

    original_other_check = container_fix.account_purchase_service.validate_other_account.check_valid
    original_universal_check = (
        container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product
    )

    async def fake_other_check(*args, **kwargs):
        return True

    async def fake_universal_check(*args, **kwargs):
        return True

    container_fix.account_purchase_service.validate_other_account.check_valid = fake_other_check
    container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = fake_universal_check
    try:
        account_result = await container_fix.purchase_service.purchase(
            user_id=account_user.user_id,
            category_id=account_category.category_id,
            quantity_products=2,
            promo_code_id=None,
            product_type=ProductType.ACCOUNT,
            language="ru",
        )
        universal_result = await container_fix.purchase_service.purchase(
            user_id=universal_user.user_id,
            category_id=universal_category.category_id,
            quantity_products=2,
            promo_code_id=None,
            product_type=ProductType.UNIVERSAL,
            language="ru",
        )
    finally:
        container_fix.account_purchase_service.validate_other_account.check_valid = original_other_check
        container_fix.universal_purchase_service.validations_universal_products.check_valid_universal_product = original_universal_check

    assert account_result is True
    assert universal_result is True

    account_user_db = await container_fix.session_db.get(Users, account_user.user_id)
    universal_user_db = await container_fix.session_db.get(Users, universal_user.user_id)
    assert account_user_db.balance == account_user.balance - 200
    assert universal_user_db.balance == universal_user.balance - 300
