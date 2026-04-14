import pytest
from sqlalchemy import select

import src.application.models.purchases.accounts.account_purchase_service as account_purchase_module
from src.database.models.categories import AccountServiceType, StorageStatus
from src.database.models.categories.product_account import AccountStorage
from src.database.models.categories.main_category_and_product import PurchaseRequests, Purchases
from src.database.models.users import BalanceHolder
from src.database.models.users.models_users import Users
from src.database.models.categories.product_account import SoldAccounts
from tests.helpers.fixtures.helper_fixture import (
    container_fix,
    create_category,
    create_new_user,
    create_product_account,
)


@pytest.mark.asyncio
async def test_account_purchase_service_start_purchase_and_finalize_success(
    container_fix,
    create_category,
    create_new_user,
    create_product_account,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=2_000)
    category = await create_category(
        container_fix,
        is_product_storage=True,
        price=100,
        cost_price=40,
        type_account_service=AccountServiceType.OTHER,
    )

    original_check_valid = container_fix.account_purchase_service.validate_other_account.check_valid

    async def fake_check_valid(*args, **kwargs):
        return True

    container_fix.account_purchase_service.validate_other_account.check_valid = fake_check_valid

    products = []
    try:
        for phone_suffix in ("01", "02"):
            product, _ = await create_product_account(
                category_id=category.category_id,
                type_account_service=AccountServiceType.OTHER,
                phone_number=f"+79991110{phone_suffix}",
            )
            products.append(product)

        start_result = await container_fix.account_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_accounts=2,
            promo_code_id=None,
        )
        assert start_result.purchase_request_id is not None
        assert len(start_result.product_accounts) == 2
        assert start_result.total_amount == 200
        assert start_result.user_balance_before == user.balance
        assert start_result.user_balance_after == user.balance - 200

        finalized = await container_fix.account_purchase_service.finalize_purchase(user.user_id, start_result)
        assert finalized is True
    finally:
        container_fix.account_purchase_service.validate_other_account.check_valid = original_check_valid

    request_db = await container_fix.session_db.get(PurchaseRequests, start_result.purchase_request_id)
    assert request_db.status == "completed"

    holder_db = await container_fix.session_db.execute(
        select(BalanceHolder).where(BalanceHolder.purchase_request_id == start_result.purchase_request_id)
    )
    assert holder_db.scalar_one().status == "used"

    sold_db = await container_fix.session_db.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
    assert len(sold_db.scalars().all()) == 2

    purchase_db = await container_fix.session_db.execute(select(Purchases).where(Purchases.user_id == user.user_id))
    assert len(purchase_db.scalars().all()) == 2

    storage_db = await container_fix.session_db.execute(
        select(AccountStorage).where(AccountStorage.account_storage_id.in_([p.account_storage_id for p in products]))
    )
    assert all(item.status == StorageStatus.BOUGHT for item in storage_db.scalars().all())

    bought_path = container_fix.path_builder.build_path_account(
        status=StorageStatus.BOUGHT,
        type_account_service=products[0].account_storage.type_account_service,
        uuid=products[0].account_storage.storage_uuid,
        as_path=True,
    )
    assert bought_path.exists()


@pytest.mark.asyncio
async def test_account_purchase_service_cancel_purchase_request_restores_state(
    container_fix,
    create_category,
    create_new_user,
    create_product_account,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=1_500)
    category = await create_category(
        container_fix,
        is_product_storage=True,
        price=100,
        cost_price=40,
        type_account_service=AccountServiceType.OTHER,
    )

    original_check_valid = container_fix.account_purchase_service.validate_other_account.check_valid

    async def fake_check_valid(*args, **kwargs):
        return True

    container_fix.account_purchase_service.validate_other_account.check_valid = fake_check_valid
    product, _ = await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
    )

    try:
        start_result = await container_fix.account_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_accounts=1,
            promo_code_id=None,
        )

        await container_fix.account_purchase_service.cancel_purchase_request(
            user_id=user.user_id,
            category_id=category.category_id,
            mapping=[],
            sold_account_ids=[],
            purchase_ids=[],
            total_amount=start_result.total_amount,
            purchase_request_id=start_result.purchase_request_id,
            product_accounts=start_result.product_accounts,
        )
    finally:
        container_fix.account_purchase_service.validate_other_account.check_valid = original_check_valid

    request_db = await container_fix.session_db.get(PurchaseRequests, start_result.purchase_request_id)
    assert request_db.status == "failed"

    holder_db = await container_fix.session_db.execute(
        select(BalanceHolder).where(BalanceHolder.purchase_request_id == start_result.purchase_request_id)
    )
    assert holder_db.scalar_one().status == "released"

    user_db = await container_fix.session_db.get(Users, user.user_id)
    assert user_db.balance == user.balance

    restored_storage = await container_fix.session_db.get(AccountStorage, product.account_storage_id)
    assert restored_storage.status == StorageStatus.FOR_SALE


@pytest.mark.asyncio
async def test_account_purchase_service_verify_reserved_accounts_replaces_invalid_and_deletes(
    container_fix,
    create_category,
    create_new_user,
    create_product_account,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=2_000)
    category = await create_category(
        container_fix,
        is_product_storage=True,
        price=100,
        cost_price=40,
        type_account_service=AccountServiceType.OTHER,
    )

    spare_product, spare_full = await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
    )
    await create_product_account(category_id=category.category_id, type_account_service=AccountServiceType.OTHER)
    _, reserved_two = await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
    )

    original_check_valid = container_fix.account_purchase_service.validate_other_account.check_valid

    async def fake_check_valid(account, *args, **kwargs):
        return getattr(account, "encrypted_key", "") != "broken"

    container_fix.account_purchase_service.validate_other_account.check_valid = fake_check_valid
    data = await container_fix.account_purchase_service.start_purchase(
        user_id=user.user_id,
        category_id=category.category_id,
        quantity_accounts=2,
        promo_code_id=None,
    )

    data.product_accounts[0].account_storage.encrypted_key = "broken"
    try:
        verified = await container_fix.account_purchase_service.verify_reserved_accounts(
            data.product_accounts,
            data.type_service_account,
            data.purchase_request_id,
        )
        assert verified is not False
        assert len(verified) == 2
        assert any(item.account_storage.account_storage_id == spare_full.account_storage.account_storage_id for item in verified)

        spare_storage = await container_fix.session_db.get(AccountStorage, spare_product.account_storage_id)
        assert spare_storage.status == StorageStatus.RESERVED
    finally:
        container_fix.account_purchase_service.validate_other_account.check_valid = original_check_valid


@pytest.mark.asyncio
async def test_account_purchase_service_verify_reserved_accounts_returns_false_without_candidates(
    container_fix,
    create_category,
    create_new_user,
    create_product_account,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=2_000)
    category = await create_category(
        container_fix,
        is_product_storage=True,
        price=100,
        cost_price=40,
        type_account_service=AccountServiceType.OTHER,
    )

    original_check_valid = container_fix.account_purchase_service.validate_other_account.check_valid

    async def fake_check_valid(account, *args, **kwargs):
        return getattr(account, "encrypted_key", "") != "broken"

    container_fix.account_purchase_service.validate_other_account.check_valid = fake_check_valid

    await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
    )

    try:
        data = await container_fix.account_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_accounts=1,
            promo_code_id=None,
        )

        data.product_accounts[0].account_storage.encrypted_key = "broken"

        verified = await container_fix.account_purchase_service.verify_reserved_accounts(
            data.product_accounts,
            data.type_service_account,
            data.purchase_request_id,
        )
        assert verified is False

        bad_storage = await container_fix.session_db.get(AccountStorage, data.product_accounts[0].account_storage.account_storage_id)
        assert bad_storage.status == StorageStatus.DELETED
    finally:
        container_fix.account_purchase_service.validate_other_account.check_valid = original_check_valid


@pytest.mark.asyncio
async def test_account_purchase_service_check_account_validity_real_branches(
    container_fix,
    create_category,
    create_product_account,
):
    await container_fix.session_db.rollback()
    category = await create_category(
        container_fix,
        is_product_storage=True,
        type_account_service=AccountServiceType.OTHER,
    )
    _, telegram_full = await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
    )
    _, other_full = await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
    )

    original_tg = container_fix.account_purchase_service.validate_tg_account.check_account_validity
    original_other = container_fix.account_purchase_service.validate_other_account.check_valid

    async def fake_tg_true(*args, **kwargs):
        return True

    async def fake_tg_false(*args, **kwargs):
        return False

    async def fake_other_true(*args, **kwargs):
        return True

    container_fix.account_purchase_service.validate_tg_account.check_account_validity = fake_tg_true
    container_fix.account_purchase_service.validate_other_account.check_valid = fake_other_true
    try:
        assert await container_fix.account_purchase_service.check_account_validity(
            telegram_full.account_storage,
            AccountServiceType.TELEGRAM,
            StorageStatus.FOR_SALE,
        ) is True

        container_fix.account_purchase_service.validate_tg_account.check_account_validity = fake_tg_false
        assert await container_fix.account_purchase_service.check_account_validity(
            telegram_full.account_storage,
            AccountServiceType.TELEGRAM,
            StorageStatus.FOR_SALE,
        ) is False

        assert await container_fix.account_purchase_service.check_account_validity(
            other_full.account_storage,
            AccountServiceType.OTHER,
            StorageStatus.FOR_SALE,
        ) is True
    finally:
        container_fix.account_purchase_service.validate_tg_account.check_account_validity = original_tg
        container_fix.account_purchase_service.validate_other_account.check_valid = original_other


@pytest.mark.asyncio
async def test_account_purchase_service_finalize_failure_uses_real_cancel_path(
    container_fix,
    create_category,
    create_new_user,
    create_product_account,
):
    await container_fix.session_db.rollback()
    user = await create_new_user(balance=2_000)
    category = await create_category(
        container_fix,
        is_product_storage=True,
        price=100,
        cost_price=40,
        type_account_service=AccountServiceType.OTHER,
    )

    original_check_valid = container_fix.account_purchase_service.validate_other_account.check_valid

    async def fake_check_valid(*args, **kwargs):
        return True

    container_fix.account_purchase_service.validate_other_account.check_valid = fake_check_valid
    await create_product_account(category_id=category.category_id, type_account_service=AccountServiceType.OTHER)
    await create_product_account(category_id=category.category_id, type_account_service=AccountServiceType.OTHER)

    try:
        start_result = await container_fix.account_purchase_service.start_purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_accounts=2,
            promo_code_id=None,
        )
    finally:
        container_fix.account_purchase_service.validate_other_account.check_valid = original_check_valid

    original_move_file = account_purchase_module.move_file

    async def fake_move_file(*args, **kwargs):
        return False

    account_purchase_module.move_file = fake_move_file
    try:
        finalized = await container_fix.account_purchase_service.finalize_purchase(user.user_id, start_result)
        assert finalized is False
    finally:
        account_purchase_module.move_file = original_move_file

    request_db = await container_fix.session_db.get(PurchaseRequests, start_result.purchase_request_id)
    assert request_db.status == "failed"

    holder_db = await container_fix.session_db.execute(
        select(BalanceHolder).where(BalanceHolder.purchase_request_id == start_result.purchase_request_id)
    )
    assert holder_db.scalar_one().status == "released"

    user_db = await container_fix.session_db.get(Users, user.user_id)
    assert user_db.balance == user.balance
