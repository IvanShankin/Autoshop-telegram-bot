import orjson
import pytest

import src.services.redis.filling_redis as filling
from tests.helpers.helper_functions import comparison_models
from src.services.database.discounts.models import SmallVoucher
from src.services.database.users.models import  BannedAccounts
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_filling_main_categories(create_category):
    category = await create_category(filling_redis=False, is_main=True)

    # Execute
    await filling.filling_main_categories()

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"main_categories:ru"
        )
    await comparison_models(category.model_dump(), orjson.loads(val)[0], ['quantity_product_account'])

@pytest.mark.asyncio
async def test_filling_categories_by_parent(create_category):
    category_parent = await create_category(filling_redis=False)
    category = await create_category(filling_redis=False, parent_id=category_parent.category_id)

    # Execute
    await filling.filling_categories_by_parent()

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"categories_by_parent:{category_parent.category_id}:ru"
        )
    await comparison_models(category.model_dump(), orjson.loads(val)[0], ['quantity_product_account'])


@pytest.mark.asyncio
async def test_filling_category_by_category(create_category):
    category = await create_category(filling_redis=False, language='ru')

    await filling.filling_category_by_category()

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"category:{category.category_id}:ru"
        )
    await comparison_models(category.model_dump(), orjson.loads(val), ['quantity_product_account'])


@pytest.mark.asyncio
async def test_filling_product_by_category_id(create_category, create_product):
    category = await create_category(filling_redis=False, language='ru')

    products = []
    for i in range(3):
        product = await create_product(
            filling_redis=False,
            category_id=category.category_id,
        )
        products.append(product)

    other_product = await create_product(filling_redis=False)

    await filling.filling_product_by_category_id()

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"products_by_category:{category.category_id}"
        )
        redis_result = orjson.loads(val)

    for prod in products:
        assert prod.to_dict() in redis_result

    assert not other_product in redis_result


@pytest.mark.asyncio
async def test_filling_product_accounts_by_product_id(create_product, create_product_account):
    product = await create_product(filling_redis=False)

    account_products = []
    for i in range(3):
        product, _ = await create_product_account(
            filling_redis=False,
            product_id=product.product_id,
        )
        account_products.append(product)

    other_account_product = await create_product(filling_redis=False)

    await filling.filling_product_accounts_by_product_id()

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"product_accounts_by_product:{product.product_id}"
        )
        redis_result = orjson.loads(val)

    for prod in account_products:
        assert any(comparison_models(prod.to_dict(), redis)  for redis in redis_result )

    assert not other_account_product in redis_result


@pytest.mark.asyncio
async def test_filling_product_account_by_account_id(create_product_account, create_category):
    category = await create_category(is_product_storage=True)
    _, product = await create_product_account(
        filling_redis=False,
        category_id=category.category_id,
    )

    await filling.filling_product_account_by_account_id(product.account_id)

    async with get_redis() as session_redis:
        val = await session_redis.get(f"product_accounts_by_account_id:{product.account_id}")

    await comparison_models(product.model_dump(), orjson.loads(val))


@pytest.mark.asyncio
async def test_filling_sold_accounts_by_owner_id(create_new_user, create_sold_account):
    # Setup
    user = await create_new_user()
    sold_account_1, _ = await create_sold_account(filling_redis=False, owner_id=user.user_id)
    sold_account_2, _ = await create_sold_account(filling_redis=False, owner_id=user.user_id)
    sold_account_3, _ = await create_sold_account(filling_redis=False, is_active=False, owner_id=user.user_id)

    # Execute
    await filling.filling_sold_accounts_by_owner_id(user.user_id)

    # Assert
    async with get_redis() as session_redis:
        key = f"sold_accounts_by_owner_id:{user.user_id}:ru"
        val = await session_redis.get(key)

    assert val is not None, f"missing redis key {key}"
    items = orjson.loads(val)

    assert 2 == len(items)

    await comparison_models(sold_account_2.model_dump(), items[0])


@pytest.mark.asyncio
async def test_filling_sold_account_by_account_id(create_sold_account):
    _, sold_account = await create_sold_account(filling_redis=False)
    await filling.filling_sold_account_by_account_id(sold_account.sold_account_id)

    # Assert
    async with get_redis() as session_redis:
        key = f"sold_accounts_by_accounts_id:{sold_account.sold_account_id}:ru"
        val = await session_redis.get(key)

    data = orjson.loads(val)
    await comparison_models(sold_account.model_dump(), data)


class TestFillRedisSingleObjects():
    """Тесты для заполнения Redis одиночными объектами"""

    @pytest.mark.asyncio
    async def test_filling_admins(self, create_new_user, create_admin_fix):
        user = await create_new_user(user_name="admin_user", union_ref_code = "admin_ref")
        admin = await create_admin_fix(filling_redis=False, user_id=user.user_id)

        await filling.filling_admins()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"admin:{user.user_id}")

        assert val

    @pytest.mark.asyncio
    async def test_filling_banned_accounts(self, create_new_user):
        user = await create_new_user(user_name="banned_user", union_ref_code = "banned_ref")
        banned = BannedAccounts(user_id=user.user_id, reason="test ban")
        async with get_db() as session_db:
            session_db.add(banned)
            await session_db.commit()


        await filling.filling_banned_accounts()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"banned_account:{user.user_id}")

        assert val


    @pytest.mark.asyncio
    async def test_filling_promo_code(self, create_promo_code):
        promo_code = await create_promo_code()

        await filling.filling_promo_code()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"promo_code:{promo_code.activation_code}")

        await comparison_models(promo_code.to_dict(), orjson.loads(val))

    @pytest.mark.asyncio
    async def test_filling_vouchers(self, create_new_user, create_voucher):
        user = await create_new_user()
        voucher = await create_voucher(filling_redis=False, creator_id=user.user_id)

        await filling.filling_vouchers()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"voucher:{voucher.activation_code}")

        await comparison_models(voucher.to_dict(), orjson.loads(val))


# @pytest.mark.asyncio
# async def test_filling_product_by_category_id(create_product_account, create_category):
#     category = await create_category(filling_redis=False)
#     create_product_account_1, _ = await create_product_account(filling_redis=False, category_id = category.category_id)
#     create_product_account_2, _ = await create_product_account(filling_redis=False, category_id = category.category_id)
#
#     # Execute
#     await filling.filling_product_by_category_id()
#
#     # Assert
#     async with get_redis() as session_redis:
#         val = await session_redis.get(f"product_accounts_by_category_id:{category.category_id}")
#
#     data = orjson.loads(val)
#     assert len(data) == 2
#
#     await comparison_models(create_product_account_1.to_dict(), data[0])
#     await comparison_models(create_product_account_2.to_dict(), data[1])

@pytest.mark.asyncio
async def test_filling_user(create_new_user):
    user = await create_new_user()
    await filling.filling_user(user)

    async with get_redis() as session_redis:
        user_redis = await session_redis.get(f'user:{user.user_id}')
        await comparison_models(user, orjson.loads(user_redis))


@pytest.mark.asyncio
async def test_filling_all_types_payments(create_type_payment):
    type_payment_1 = await create_type_payment(filling_redis=False, name_for_user="name_2", index=1)
    type_payment_0 = await create_type_payment(filling_redis=False, name_for_user="name_1", index=0)
    type_payment_2 = await create_type_payment(filling_redis=False, name_for_user="name_1", index=2)

    await filling.filling_all_types_payments()

    async with get_redis() as session_redis:
        value = await session_redis.get("all_types_payments")
        assert value
        all_types = orjson.loads(value)

    # проверяем правильность фильтрации по индексу
    assert type_payment_0.to_dict() == all_types[0]
    assert type_payment_1.to_dict() == all_types[1]
    assert type_payment_2.to_dict() == all_types[2]


@pytest.mark.asyncio
async def test_filling_types_payments_by_id(create_type_payment):
    type_payment_1 = await create_type_payment(filling_redis=False, name_for_user="name_1")

    await filling.filling_types_payments_by_id(type_payment_1.type_payment_id)

    async with get_redis() as session_redis:
        value = await session_redis.get(f"type_payments:{type_payment_1.type_payment_id}")
        assert value
        type_payment = orjson.loads(value)

    assert type_payment == type_payment_1.to_dict()


@pytest.mark.asyncio
async def test_filling_voucher_by_user_id(patch_fake_aiogram, create_new_user, create_voucher):
    user = await create_new_user()
    voucher_1 = await create_voucher(filling_redis=False, creator_id=user.user_id)
    voucher_2 = await create_voucher(filling_redis=False, creator_id=user.user_id)
    voucher_3 = await create_voucher(filling_redis=False, creator_id=user.user_id)

    await filling.filling_voucher_by_user_id(user.user_id)

    async with get_redis() as session_redis:
        value = await session_redis.get(f"voucher_by_user:{user.user_id}")
        assert value
        vouchers = orjson.loads(value)

        # проверяем сортировку по дате создания (desc)
        assert SmallVoucher.from_orm_model(voucher_1).model_dump() == vouchers[2]
        assert SmallVoucher.from_orm_model(voucher_2).model_dump() == vouchers[1]
        assert SmallVoucher.from_orm_model(voucher_3).model_dump() == vouchers[0]
