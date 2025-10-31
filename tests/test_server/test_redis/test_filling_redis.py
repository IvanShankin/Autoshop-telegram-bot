import orjson
import pytest
from sqlalchemy import select

import src.services.redis.filling_redis as filling
from tests.helpers.helper_functions import comparison_models
from src.config import UI_IMAGES
from src.services.database.core.filling_database import filling_ui_image
from src.services.database.discounts.models import SmallVoucher
from src.services.database.system.models import UiImages
from src.services.database.users.models import  BannedAccounts
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_filling_account_categories_by_category_id(create_account_category):
    category = await create_account_category(filling_redis=False)

    # Execute
    await filling.filling_account_categories_by_category_id()

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"account_categories_by_category_id:{category.account_category_id}:ru"
        )
    await comparison_models(category.model_dump(), orjson.loads(val))

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



@pytest.mark.asyncio
async def test_filling_account_categories_by_service_id(create_account_service, create_account_category):
    # Setup
    account_service = await create_account_service(filling_redis=False)
    category_1 = await create_account_category(filling_redis=False, account_service_id=account_service.account_service_id, language='ru')
    category_2 = await create_account_category(filling_redis=False, account_service_id=account_service.account_service_id, language='ru')

    # Execute
    await filling.filling_account_categories_by_service_id()

    async with get_redis() as session_redis:
        key = f"account_categories_by_service_id:{account_service.account_service_id}:ru"
        val = await session_redis.get(key)

    categories_list = orjson.loads(val)
    assert len(categories_list) == 2
    await comparison_models(category_1.model_dump(), categories_list[0])
    await comparison_models(category_2.model_dump(), categories_list[1])

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
    async def test_filling_type_account_services(self, create_type_account_service):
        type_service = await create_type_account_service()

        await filling.filling_type_account_services()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"type_account_service:{type_service.type_account_service_id}")

        await comparison_models(type_service.to_dict(), orjson.loads(val))

    @pytest.mark.asyncio
    async def test_filling_account_services(self, create_account_service):
        account_service = await create_account_service()

        await filling.filling_account_services()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"account_service:{account_service.type_account_service_id}")

        await comparison_models(account_service.to_dict(), orjson.loads(val))


    @pytest.mark.asyncio
    async def test_filling_product_account_by_account_id(self, create_product_account, create_account_category,create_type_account_service):
        type_account_service = await create_type_account_service()
        category = await create_account_category(is_accounts_storage=True)
        _, product = await create_product_account(
            filling_redis=False,
            type_account_service_id=type_account_service.type_account_service_id,
            account_category_id=category.account_category_id,
        )

        await filling.filling_product_account_by_account_id(product.account_id)

        async with get_redis() as session_redis:
            val = await session_redis.get(f"product_accounts_by_account_id:{product.account_id}")

        await comparison_models(product.model_dump(), orjson.loads(val))

    @pytest.mark.asyncio
    async def test_filling_promo_code(self, create_promo_code):
        promo_code = create_promo_code

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

@pytest.mark.asyncio
async def test_filling_product_accounts_by_category_id(create_product_account, create_account_category):
    category = await create_account_category(filling_redis=False)
    create_product_account_1, _ = await create_product_account(filling_redis=False, account_category_id = category.account_category_id)
    create_product_account_2, _ = await create_product_account(filling_redis=False, account_category_id = category.account_category_id)

    # Execute
    await filling.filling_product_accounts_by_category_id()

    # Assert
    async with get_redis() as session_redis:
        val = await session_redis.get(f"product_accounts_by_category_id:{category.account_category_id}")

    data = orjson.loads(val)
    assert len(data) == 2

    await comparison_models(create_product_account_1.to_dict(), data[0])
    await comparison_models(create_product_account_2.to_dict(), data[1])

@pytest.mark.asyncio
async def test_filling_user(create_new_user):
    user = await create_new_user()
    await filling.filling_user(user)

    async with get_redis() as session_redis:
        user_redis = await session_redis.get(f'user:{user.user_id}')
        await comparison_models(user, orjson.loads(user_redis))

@pytest.mark.asyncio
async def test_filling_types_account_service(create_type_account_service):
    # заполняем БД
    for key in UI_IMAGES:
        await filling_ui_image(key=key, path=UI_IMAGES[key])
        await filling.filling_ui_image(key) # тестируемая функция

    async with get_redis() as session_redis:
        async with get_db() as session_db:
            for key, value in UI_IMAGES:
                result_db = await session_db.execute(select(UiImages).where(UiImages.key == key)) 
                data_db = result_db.scalar()

                result_redis = await session_redis.get(f"ui_image:{key}")
                data_redis = orjson.loads(result_redis)

                assert data_redis == data_db.to_dict()
                assert value == data_redis['file_path']


@pytest.mark.asyncio
async def test_filling_types_account_service(create_type_account_service):
    service_1 = await create_type_account_service()
    service_2 = await create_type_account_service()

    await filling.filling_all_types_account_service()

    async with get_redis() as session_redis:
        val = await session_redis.get("types_account_service")
        list_types = orjson.loads(val)

    assert service_1.to_dict() in list_types
    assert service_2.to_dict() in list_types


@pytest.mark.asyncio
async def test_filling_all_account_services(create_account_service):
    account_service = await create_account_service()

    await filling.filling_all_account_services()

    async with get_redis() as session_redis:
        val = await session_redis.get(f"account_services")
        list_account_service = orjson.loads(val)

    assert account_service.to_dict() in list_account_service


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
