from typing import Type

import pytest
import orjson
from datetime import datetime
from dateutil.parser import parse

from src.database import Users, BannedAccounts
from src.modules.admin_actions.models import Admins
from src.modules.discounts.models import PromoCodes, Vouchers
from src.modules.selling_accounts.models import TypeAccountServices, AccountServices, AccountCategories,ProductAccounts, SoldAccounts
import src.redis_dependencies.filling_redis as filling
from src.database.database import get_db
from src.redis_dependencies.core_redis import get_redis


def comparison_dicts(model: Type, json_str: orjson):
    data_from_redis = orjson.loads(json_str)
    model_in_dict: dict = model.to_dict()

    for key in model_in_dict.keys():
        if isinstance(model_in_dict[key], datetime):  # если встретили дата
            assert model_in_dict[key] == parse(data_from_redis[key])
        else:
            assert model_in_dict[key] == data_from_redis[key]

async def added_and_refresh_in_db(object_model):
    async with get_db() as session_db:
        session_db.add(object_model)
        await session_db.commit()
        await session_db.refresh(object_model)
        return object_model

class TestFillRedisSingleObjects:
    @pytest.mark.asyncio
    async def test_filling_user(self):
        new_user = Users(username="test", language="rus", unique_referral_code="abc", balance=100, total_sum_replenishment=50,
              total_sum_from_referrals=10)
        new_user = await added_and_refresh_in_db(new_user)

        await filling.filling_users()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"user:{new_user.user_id}")

        comparison_dicts(new_user, val)

    @pytest.mark.asyncio
    async def test_filling_admins(self):
        # Сначала создаём пользователя
        user = Users(username="admin_user", language="rus", unique_referral_code="admin_ref", balance=0)
        user = await added_and_refresh_in_db(user)

        # Теперь создаём админа
        admin = await added_and_refresh_in_db(Admins(user_id=user.user_id))

        await filling.filling_admins()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"admin:{user.user_id}")

        assert val == '_'

    @pytest.mark.asyncio
    async def test_filling_banned_accounts(self):
        # Сначала создаём пользователя
        user = Users(username="banned_user", language="rus", unique_referral_code="banned_ref", balance=0)
        user = await added_and_refresh_in_db(user)

        # Теперь создаём бан
        banned = BannedAccounts(user_id=user.user_id, reason="test ban")
        banned = await added_and_refresh_in_db(banned)

        await filling.filling_banned_accounts()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"banned_account:{user.user_id}")

        assert val == '_'

    @pytest.mark.asyncio
    async def test_filling_type_account_services(self):
        type_service = TypeAccountServices(name="telegram")
        type_service = await added_and_refresh_in_db(type_service)

        await filling.filling_type_account_services()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"type_account_service:{type_service.name}")

        comparison_dicts(type_service, val)

    @pytest.mark.asyncio
    async def test_filling_account_services(self):
        # Сначала создаём тип сервиса
        type_service = TypeAccountServices(name="social_media")
        type_service = await added_and_refresh_in_db(type_service)

        # Теперь создаём сервис
        account_service = AccountServices(name="Telegram", type_account_service_id=type_service.type_account_service_id)
        account_service = await added_and_refresh_in_db(account_service)

        await filling.filling_account_services()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"account_service:{account_service.type_account_service_id}")

        comparison_dicts(account_service, val)

    @pytest.mark.asyncio
    async def test_filling_account_categories_by_category_id(self):
        # Сначала создаём тип сервиса
        type_service = TypeAccountServices(name="test_type")
        type_service = await added_and_refresh_in_db(type_service)

        # Создаём сервис
        account_service = AccountServices(name="Test Service",
                                          type_account_service_id=type_service.type_account_service_id)
        account_service = await added_and_refresh_in_db(account_service)

        # Теперь создаём категорию
        category = AccountCategories(
            account_service_id=account_service.account_service_id,
            name="Test Category",
            description="Test description",
            is_main=True,
            is_accounts_storage=False
        )
        category = await added_and_refresh_in_db(category)

        await filling.filling_account_categories_by_category_id()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"account_categories_by_category_id:{category.account_category_id}")

        comparison_dicts(category, val)

    @pytest.mark.asyncio
    async def test_filling_product_accounts_by_account_id(self):
        # Создаём всю цепочку зависимостей
        type_service = TypeAccountServices(name="product_type")
        type_service = await added_and_refresh_in_db(type_service)

        account_service = AccountServices(name="Product Service",
                                          type_account_service_id=type_service.type_account_service_id)
        account_service = await added_and_refresh_in_db(account_service)

        category = AccountCategories(
            account_service_id=account_service.account_service_id,
            name="Product Category",
            description="Product description",
            is_main=True,
            is_accounts_storage=True
        )
        category = await added_and_refresh_in_db(category)

        # Теперь создаём продукт
        product = ProductAccounts(
            type_account_service_id=type_service.type_account_service_id,
            account_category_id=category.account_category_id
        )
        product = await added_and_refresh_in_db(product)

        await filling.filling_product_accounts_by_account_id()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"product_accounts_by_account_id:{product.account_id}")

        comparison_dicts(product, val)

    @pytest.mark.asyncio
    async def test_filling_sold_accounts_by_accounts_id(self):
        # Создаём пользователя и тип сервиса
        user = Users(username="seller", language="rus", unique_referral_code="seller_ref", balance=0)
        user = await added_and_refresh_in_db(user)

        type_service = TypeAccountServices(name="sold_type")
        type_service = await added_and_refresh_in_db(type_service)

        # Создаём проданный аккаунт
        sold_account = SoldAccounts(
            owner_id=user.user_id,
            type_account_service_id=type_service.type_account_service_id,
            category_name="Test Category",
            service_name="Test Service",
            type_name="Test Type"
        )
        sold_account = await added_and_refresh_in_db(sold_account)

        await filling.filling_sold_accounts_by_accounts_id()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"sold_accounts_by_accounts_id:{sold_account.sold_account_id}")

        comparison_dicts(sold_account, val)

    @pytest.mark.asyncio
    async def test_filling_promo_code(self):
        promo = PromoCodes(
            activation_code="TEST123",
            min_order_amount=100,
            amount=10,
            is_valid=True
        )
        promo = await added_and_refresh_in_db(promo)

        await filling.filling_promo_code()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"promo_code:{promo.activation_code}")

        comparison_dicts(promo, val)

    @pytest.mark.asyncio
    async def test_filling_vouchers(self):
        # Сначала создаём пользователя
        user = Users(username="voucher_creator", language="rus", unique_referral_code="voucher_ref", balance=0)
        user = await added_and_refresh_in_db(user)

        # Теперь создаём ваучер
        voucher = Vouchers(
            activation_code="VOUCHER123",
            amount=100,
            is_valid=True,
            is_created_admin=False,
            creator_id=user.user_id
        )
        voucher = await added_and_refresh_in_db(voucher)

        await filling.filling_vouchers()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"vouchers:{voucher.activation_code}")

        comparison_dicts(voucher, val)


class TestFillRedisGroupedObjects:
    @pytest.mark.asyncio
    async def test_filling_account_categories_by_service_id(self):
        # Создаём тип сервиса
        type_service = TypeAccountServices(name="grouped_test_type")
        type_service = await added_and_refresh_in_db(type_service)

        # Создаём сервис
        account_service = AccountServices(name="Grouped Test Service",
                                          type_account_service_id=type_service.type_account_service_id)
        account_service = await added_and_refresh_in_db(account_service)

        # Создаём несколько категорий для одного сервиса
        category1 = AccountCategories(
            account_service_id=account_service.account_service_id,
            name="Category 1",
            description="Test category 1",
            is_main=True,
            is_accounts_storage=False
        )
        category1 = await added_and_refresh_in_db(category1)

        category2 = AccountCategories(
            account_service_id=account_service.account_service_id,
            name="Category 2",
            description="Test category 2",
            is_main=False,
            is_accounts_storage=True
        )
        category2 = await added_and_refresh_in_db(category2)

        await filling.filling_account_categories_by_service_id()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"account_categories_by_service_id:{account_service.account_service_id}")

        data_from_redis = orjson.loads(val)
        assert len(data_from_redis) == 2

        # Проверяем, что обе категории присутствуют
        category_ids = [cat['account_category_id'] for cat in data_from_redis]
        assert category1.account_category_id in category_ids
        assert category2.account_category_id in category_ids

    @pytest.mark.asyncio
    async def test_filling_product_accounts_by_category_id(self):
        # Создаём всю цепочку зависимостей
        type_service = TypeAccountServices(name="product_grouped_type")
        type_service = await added_and_refresh_in_db(type_service)

        account_service = AccountServices(name="Product Grouped Service",
                                          type_account_service_id=type_service.type_account_service_id)
        account_service = await added_and_refresh_in_db(account_service)

        category = AccountCategories(
            account_service_id=account_service.account_service_id,
            name="Product Grouped Category",
            description="Product grouped description",
            is_main=True,
            is_accounts_storage=True
        )
        category = await added_and_refresh_in_db(category)

        # Создаём несколько продуктов для одной категории
        product1 = ProductAccounts(
            type_account_service_id=type_service.type_account_service_id,
            account_category_id=category.account_category_id
        )
        product1 = await added_and_refresh_in_db(product1)

        product2 = ProductAccounts(
            type_account_service_id=type_service.type_account_service_id,
            account_category_id=category.account_category_id
        )
        product2 = await added_and_refresh_in_db(product2)

        await filling.filling_product_accounts_by_category_id()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"product_accounts_by_category_id:{category.account_category_id}")

        data_from_redis = orjson.loads(val)
        assert len(data_from_redis) == 2

        # Проверяем, что оба продукта присутствуют
        product_ids = [prod['account_id'] for prod in data_from_redis]
        assert product1.account_id in product_ids
        assert product2.account_id in product_ids

    @pytest.mark.asyncio
    async def test_filling_sold_accounts_by_owner_id(self):
        # Создаём пользователя и тип сервиса
        user = Users(username="grouped_seller", language="rus", unique_referral_code="grouped_seller_ref", balance=0)
        user = await added_and_refresh_in_db(user)

        type_service = TypeAccountServices(name="grouped_sold_type")
        type_service = await added_and_refresh_in_db(type_service)

        # Создаём несколько проданных аккаунтов для одного владельца
        sold_account1 = SoldAccounts(
            owner_id=user.user_id,
            type_account_service_id=type_service.type_account_service_id,
            category_name="Test Category 1",
            service_name="Test Service 1",
            type_name="Test Type 1",
            is_deleted=False
        )
        sold_account1 = await added_and_refresh_in_db(sold_account1)

        sold_account2 = SoldAccounts(
            owner_id=user.user_id,
            type_account_service_id=type_service.type_account_service_id,
            category_name="Test Category 2",
            service_name="Test Service 2",
            type_name="Test Type 2",
            is_deleted=False
        )
        sold_account2 = await added_and_refresh_in_db(sold_account2)

        await filling.filling_sold_accounts_by_owner_id()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"sold_accounts_by_owner_id:{user.user_id}")

        data_from_redis = orjson.loads(val)
        assert len(data_from_redis) == 2

        # Проверяем, что оба проданных аккаунта присутствуют
        sold_account_ids = [acc['sold_account_id'] for acc in data_from_redis]
        assert sold_account1.sold_account_id in sold_account_ids
        assert sold_account2.sold_account_id in sold_account_ids

    @pytest.mark.asyncio
    async def test_filling_sold_accounts_by_owner_id_with_filter(self):
        # Создаём пользователя и тип сервиса
        user = Users(username="filtered_seller", language="rus", unique_referral_code="filtered_seller_ref", balance=0)
        user = await added_and_refresh_in_db(user)

        type_service = TypeAccountServices(name="filtered_sold_type")
        type_service = await added_and_refresh_in_db(type_service)

        # Создаём несколько проданных аккаунтов для одного владельца
        sold_account1 = SoldAccounts(
            owner_id=user.user_id,
            type_account_service_id=type_service.type_account_service_id,
            category_name="Test Category 1",
            service_name="Test Service 1",
            type_name="Test Type 1",
            is_deleted=False
        )
        sold_account1 = await added_and_refresh_in_db(sold_account1)

        sold_account2 = SoldAccounts(
            owner_id=user.user_id,
            type_account_service_id=type_service.type_account_service_id,
            category_name="Test Category 2",
            service_name="Test Service 2",
            type_name="Test Type 2",
            is_deleted=True  # Этот не должен пройти фильтрацию
        )
        sold_account2 = await added_and_refresh_in_db(sold_account2)

        await filling.filling_sold_accounts_by_owner_id()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"sold_accounts_by_owner_id:{user.user_id}")

        data_from_redis = orjson.loads(val)
        assert len(data_from_redis) == 1  # Только один аккаунт должен пройти фильтр

        # Проверяем, что только не удалённый аккаунт присутствует
        sold_account_ids = [acc['sold_account_id'] for acc in data_from_redis]
        assert sold_account1.sold_account_id in sold_account_ids
        assert sold_account2.sold_account_id not in sold_account_ids

    @pytest.mark.asyncio
    async def test_filling_multiple_services_categories(self):
        # Создаём несколько типов сервисов
        type_service1 = TypeAccountServices(name="service_type_1")
        type_service1 = await added_and_refresh_in_db(type_service1)

        type_service2 = TypeAccountServices(name="service_type_2")
        type_service2 = await added_and_refresh_in_db(type_service2)

        # Создаём сервисы для каждого типа
        account_service1 = AccountServices(name="Service 1",
                                           type_account_service_id=type_service1.type_account_service_id)
        account_service1 = await added_and_refresh_in_db(account_service1)

        account_service2 = AccountServices(name="Service 2",
                                           type_account_service_id=type_service2.type_account_service_id)
        account_service2 = await added_and_refresh_in_db(account_service2)

        # Создаём категории для каждого сервиса
        category1 = AccountCategories(
            account_service_id=account_service1.account_service_id,
            name="Category for Service 1",
            description="Test category",
            is_main=True,
            is_accounts_storage=False
        )
        category1 = await added_and_refresh_in_db(category1)

        category2 = AccountCategories(
            account_service_id=account_service2.account_service_id,
            name="Category for Service 2",
            description="Test category",
            is_main=True,
            is_accounts_storage=False
        )
        category2 = await added_and_refresh_in_db(category2)

        await filling.filling_account_categories_by_service_id()

        # Проверяем, что категории сгруппированы по своим сервисам
        async with get_redis() as session_redis:
            val1 = await session_redis.get(f"account_categories_by_service_id:{account_service1.account_service_id}")
            val2 = await session_redis.get(f"account_categories_by_service_id:{account_service2.account_service_id}")

        data_from_redis1 = orjson.loads(val1)
        data_from_redis2 = orjson.loads(val2)

        assert len(data_from_redis1) == 1
        assert len(data_from_redis2) == 1
        assert data_from_redis1[0]['account_category_id'] == category1.account_category_id
        assert data_from_redis2[0]['account_category_id'] == category2.account_category_id
