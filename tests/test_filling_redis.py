import asyncio
from datetime import datetime
from typing import Type, Any

import orjson
import pytest
from dateutil.parser import parse

import src.redis_dependencies.filling_redis as filling
from src.services.selling_accounts.models.models_with_tranlslate import SoldAccountsFull
from src.services.users.models import Users, BannedAccounts
from src.services.database.database import get_db
from src.services.admins.models import Admins
from src.services.discounts.models import PromoCodes, Vouchers
from src.services.selling_accounts.models import (
    TypeAccountServices, AccountServices, AccountCategories,
    ProductAccounts, SoldAccounts, AccountCategoryTranslation, SoldAccountsTranslation
)
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.helper_fixture import create_sold_account, create_new_user

class TestBase:
    """Базовый класс для тестов с общими методами"""

    @staticmethod
    async def add_and_refresh(object_model: Any) -> Any:
        """Добавляет объект в БД и обновляет его"""
        async with get_db() as session_db:
            session_db.add(object_model)
            await session_db.commit()
            await session_db.refresh(object_model)
            return object_model

    @staticmethod
    def compare_dicts(model: Type, json_str: bytes) -> None:
        """Сравнивает словарь модели с данными из Redis"""
        data_from_redis = orjson.loads(json_str)
        model_dict = model.to_dict()

        for key in model_dict.keys():
            if isinstance(model_dict[key], datetime):
                assert model_dict[key] == parse(data_from_redis[key])
            else:
                assert model_dict[key] == data_from_redis[key]

    async def create_basic_user(self, username: str, referral_code: str) -> Users:
        """Создает базового пользователя"""
        return await self.add_and_refresh(
            Users(
                username=username,
                language="ru",
                unique_referral_code=referral_code,
                balance=0
            )
        )

    async def create_type_service(self, name: str) -> TypeAccountServices:
        """Создает тип сервиса"""
        return await self.add_and_refresh(TypeAccountServices(name=name))

    async def create_account_service(self, type_service: TypeAccountServices, name: str) -> AccountServices:
        """Создает сервис аккаунта"""
        return await self.add_and_refresh(
            AccountServices(
                name=name,
                type_account_service_id=type_service.type_account_service_id
            )
        )

    async def create_account_category(self, account_service: AccountServices,
                                      index: int = 0,
                                      show: bool = True,
                                      is_main: bool = True,
                                      is_storage: bool = False) -> AccountCategories:
        """Создает категорию аккаунта"""
        return await self.add_and_refresh(
            AccountCategories(
                account_service_id=account_service.account_service_id,
                index=index,
                show=show,
                is_main=is_main,
                is_accounts_storage=is_storage
            )
        )


class TestFillRedisSingleObjectsMultilang(TestBase):
    """Тесты для заполнения Redis одиночными объектами с мультиязычностью"""

    @pytest.mark.asyncio
    async def test_filling_account_categories_by_category_id(self):
        # Setup
        type_service = await self.create_type_service("test_type")
        account_service = await self.create_account_service(type_service, "Test Service")
        category = await self.create_account_category(account_service)

        translations = []
        for lang, name, description in [
            ('ru', "Тестовая категория", "Тестовое описание"),
            ('en', "Test Category", "Test description")
        ]:
            translation = await self.add_and_refresh(
                AccountCategoryTranslation(
                    account_category_id=category.account_category_id,
                    lang=lang,
                    name=name,
                    description=description
                )
            )
            translations.append(translation)

        # Execute
        await filling.filling_account_categories_by_category_id()

        # Assert
        for translate in translations:
            async with get_redis() as session_redis:
                val = await session_redis.get(
                    f"account_categories_by_category_id:{category.account_category_id}:{translate.lang}"
                )

            data = orjson.loads(val)
            expected_data = {
                "account_category_id": translate.account_category_id,
                "account_service_id": category.account_service_id,
                "name": translate.name,
                "description": translate.description,
                "is_main": category.is_main,
                "is_accounts_storage": category.is_accounts_storage
            }

            for key, expected_value in expected_data.items():
                assert data[key] == expected_value

    @pytest.mark.asyncio
    async def test_filling_sold_accounts_by_accounts_id(self):
        # Setup
        user = await self.create_basic_user("seller", "seller_ref")
        type_service = await self.create_type_service("sold_type")

        sold_account = await self.add_and_refresh(
            SoldAccounts(
                owner_id=user.user_id,
                type_account_service_id=type_service.type_account_service_id,
                is_deleted=False
            )
        )

        translations = []
        for lang, name, description in [
            ('ru', "Имя RU", "Описание RU"),
            ('en', "Name EN", "Description EN")
        ]:
            translation = await self.add_and_refresh(
                SoldAccountsTranslation(
                    sold_account_id=sold_account.sold_account_id,
                    lang=lang,
                    name=name,
                    description=description
                )
            )
            translations.append(translation)

        # Execute
        await filling.filling_sold_accounts_by_accounts_id()

        # Assert
        for tr in translations:
            async with get_redis() as session_redis:
                key = f"sold_accounts_by_accounts_id:{sold_account.sold_account_id}:{tr.lang}"
                val = await session_redis.get(key)

            assert val is not None, f"missing redis key {key}"
            data = orjson.loads(val)

            expected_fields = {
                "sold_account_id": sold_account.sold_account_id,
                "owner_id": sold_account.owner_id,
                "name": tr.name,
                "description": tr.description
            }

            for field, expected_value in expected_fields.items():
                assert data[field] == expected_value


class TestFillRedisGroupedObjectsMultilang(TestBase):
    """Тесты для заполнения Redis сгруппированными объектами с мультиязычностью"""

    @pytest.mark.asyncio
    async def test_filling_account_categories_by_service_id(self):
        # Setup
        type_service = await self.create_type_service("grouped_test_type")
        account_service = await self.create_account_service(type_service, "Grouped Test Service")

        # Create categories with translations
        categories_data = [
            # category 1: only RU
            (True, False, [('ru', "Кат 1 RU", "Описание 1 RU")]),
            # category 2: both RU and EN
            (False, True, [
                ('ru', "Кат 2 RU", "Описание 2 RU"),
                ('en', "Cat 2 EN", "Desc 2 EN")
            ])
        ]

        for is_main, is_storage, translations_data in categories_data:
            category = await self.create_account_category(account_service, is_main = is_main, is_storage = is_storage)

            for lang, name, description in translations_data:
                await self.add_and_refresh(
                    AccountCategoryTranslation(
                        account_category_id=category.account_category_id,
                        lang=lang,
                        name=name,
                        description=description
                    )
                )

        # Execute
        await filling.filling_account_categories_by_service_id()

        # Assert
        test_cases = [
            ('ru', 2),  # Both categories have RU translations
            ('en', 1)  # Only second category has EN translation
        ]

        for lang, expected_count in test_cases:
            async with get_redis() as session_redis:
                key = f"account_categories_by_service_id:{account_service.account_service_id}:{lang}"
                val = await session_redis.get(key)

            assert val is not None, f"missing redis key {key}"
            categories_list = orjson.loads(val)
            assert len(categories_list) == expected_count

    @pytest.mark.asyncio
    async def test_filling_sold_accounts_by_owner_id(self):
        # Setup
        user = await self.create_basic_user("grouped_seller", "grouped_seller_ref")
        type_service = await self.create_type_service("grouped_sold_type")

        # Create sold accounts with translations
        accounts_data = [
            (False, "Имя А", "Описание A"),
            (False, "Имя B", "Описание B")
        ]

        sold_accounts = []
        for is_deleted, name, description in accounts_data:
            sold_account = await self.add_and_refresh(
                SoldAccounts(
                    owner_id=user.user_id,
                    type_account_service_id=type_service.type_account_service_id,
                    is_deleted=is_deleted
                )
            )
            sold_accounts.append(sold_account)

            await self.add_and_refresh(
                SoldAccountsTranslation(
                    sold_account_id=sold_account.sold_account_id,
                    lang="ru",
                    name=name,
                    description=description
                )
            )

        # Execute
        await filling.filling_sold_accounts_by_owner_id()

        # Assert
        async with get_redis() as session_redis:
            key = f"sold_accounts_by_owner_id:{user.user_id}:ru"
            val = await session_redis.get(key)

        assert val is not None, f"missing redis key {key}"
        items = orjson.loads(val)

        # Should only include non-deleted accounts
        expected_count = sum(1 for acc in sold_accounts if not acc.is_deleted)
        assert len(items) == expected_count

        actual_ids = {item["sold_account_id"] for item in items}
        expected_ids = {acc.sold_account_id for acc in sold_accounts if not acc.is_deleted}
        assert actual_ids == expected_ids

    @pytest.mark.asyncio
    async def test_filling_sold_accounts_by_owner_id_with_filter(self):
        """Тест фильтрации удаленных аккаунтов"""
        await self.test_filling_sold_accounts_by_owner_id()  # Используем общий тест


class TestFillRedisSingleObjects(TestBase):
    """Тесты для заполнения Redis одиночными объектами"""

    @pytest.mark.asyncio
    async def test_filling_user(self):
        user = await self.add_and_refresh(
            Users(
                username="test",
                language="ru",
                unique_referral_code="abc",
                balance=100,
                total_sum_replenishment=50,
                total_profit_from_referrals=10
            )
        )

        await filling.filling_users()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"user:{user.user_id}")

        self.compare_dicts(user, val)

    @pytest.mark.asyncio
    async def test_filling_admins(self):
        user = await self.create_basic_user("admin_user", "admin_ref")
        admin = await self.add_and_refresh(Admins(user_id=user.user_id))

        await filling.filling_admins()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"admin:{user.user_id}")

        assert val

    @pytest.mark.asyncio
    async def test_filling_banned_accounts(self):
        user = await self.create_basic_user("banned_user", "banned_ref")
        banned = await self.add_and_refresh(
            BannedAccounts(user_id=user.user_id, reason="test ban")
        )

        await filling.filling_banned_accounts()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"banned_account:{user.user_id}")

        assert val

    @pytest.mark.asyncio
    async def test_filling_type_account_services(self):
        type_service = await self.create_type_service("telegram")

        await filling.filling_type_account_services()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"type_account_service:{type_service.type_account_service_id}")

        self.compare_dicts(type_service, val)

    @pytest.mark.asyncio
    async def test_filling_account_services(self):
        type_service = await self.create_type_service("social_media")
        account_service = await self.create_account_service(type_service, "Telegram")

        await filling.filling_account_services()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"account_service:{account_service.type_account_service_id}")

        self.compare_dicts(account_service, val)

    @pytest.mark.asyncio
    async def test_filling_product_accounts_by_account_id(self):
        type_service = await self.create_type_service("product_type")
        account_service = await self.create_account_service(type_service, "Product Service")
        category = await self.create_account_category(account_service, is_storage=True)

        product = await self.add_and_refresh(
            ProductAccounts(
                type_account_service_id=type_service.type_account_service_id,
                account_category_id=category.account_category_id
            )
        )

        await filling.filling_product_accounts_by_account_id()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"product_accounts_by_account_id:{product.account_id}")

        self.compare_dicts(product, val)

    @pytest.mark.asyncio
    async def test_filling_promo_code(self):
        promo = await self.add_and_refresh(
            PromoCodes(
                activation_code="TEST123",
                min_order_amount=100,
                amount=10,
                is_valid=True
            )
        )

        await filling.filling_promo_code()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"promo_code:{promo.activation_code}")

        self.compare_dicts(promo, val)

    @pytest.mark.asyncio
    async def test_filling_vouchers(self):
        user = await self.create_basic_user("voucher_creator", "voucher_ref")

        voucher = await self.add_and_refresh(
            Vouchers(
                activation_code="VOUCHER123",
                amount=100,
                is_valid=True,
                is_created_admin=False,
                creator_id=user.user_id
            )
        )

        await filling.filling_vouchers()

        async with get_redis() as session_redis:
            val = await session_redis.get(f"voucher:{voucher.activation_code}")

        self.compare_dicts(voucher, val)


class TestFillRedisGroupedObjects(TestBase):
    """Тесты для заполнения Redis сгруппированными объектами"""

    @pytest.mark.asyncio
    async def test_filling_product_accounts_by_category_id(self):
        # Setup
        type_service = await self.create_type_service("product_grouped_type")
        account_service = await self.create_account_service(type_service, "Product Grouped Service")
        category = await self.create_account_category(account_service, is_storage=True)

        # Create multiple products for the same category
        products = []
        for _ in range(2):
            product = await self.add_and_refresh(
                ProductAccounts(
                    type_account_service_id=type_service.type_account_service_id,
                    account_category_id=category.account_category_id
                )
            )
            products.append(product)

        # Execute
        await filling.filling_product_accounts_by_category_id()

        # Assert
        async with get_redis() as session_redis:
            val = await session_redis.get(f"product_accounts_by_category_id:{category.account_category_id}")

        data = orjson.loads(val)
        assert len(data) == len(products)

        product_ids = {prod['account_id'] for prod in data}
        expected_ids = {product.account_id for product in products}
        assert product_ids == expected_ids


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
async def test_filling_all_account_services():
    creator = TestBase()

    type_service = await creator.create_type_service("product_grouped_type")
    account_service = await creator.create_account_service(type_service, "Product Grouped Service")
    account_service = account_service.to_dict()

    await filling.filling_all_account_services()

    async with get_redis() as session_redis:
        val = await session_redis.get(f"account_services")
        list_account_service = orjson.loads(val)

    assert account_service in list_account_service


@pytest.mark.asyncio
async def test_filling_sold_account_only_one_owner(create_new_user, create_sold_account):
    user = await create_new_user()

    account_1: SoldAccountsFull = await create_sold_account(
        filling_redis=False,
        owner_id=user.user_id,
        name="account_1"
    )
    await asyncio.sleep(0.1)
    account_2: SoldAccountsFull = await create_sold_account(
        filling_redis=False,
        owner_id=user.user_id,
        name="account_2"
    )
    await asyncio.sleep(0.1)
    account_3: SoldAccountsFull = await create_sold_account(
        filling_redis=False,
        owner_id=user.user_id,
        name="account_3"
    )

    await create_sold_account(filling_redis=False) # аккаунт с другим пользователем

    await filling.filling_sold_account_only_one_owner(user.user_id)

    async with get_redis() as session_redis:
        val = await session_redis.get(f'sold_accounts_by_owner_id:{account_1.owner_id}:ru')
        list_account = orjson.loads(val)

    # должен быть именно такой порядок (отсортировано по убыванию даты)
    assert list_account[0] == account_3.model_dump()
    assert list_account[1] == account_2.model_dump()
    assert list_account[2] == account_1.model_dump()

@pytest.mark.asyncio
async def test_filling_sold_account_only_one(create_new_user, create_sold_account):
    user = await create_new_user()

    account: SoldAccountsFull = await create_sold_account(
        filling_redis=False,
        owner_id=user.user_id,
        name="account"
    )
    await filling.filling_sold_account_only_one(account.sold_account_id, 'ru')

    async with get_redis() as session_redis:
        val = await session_redis.get(f'sold_accounts_by_accounts_id:{account.sold_account_id}:ru')
        account_redis = orjson.loads(val)

    assert account_redis == account.model_dump()

@pytest.mark.asyncio
async def test_filling_sold_account_only_one(create_type_payment):
    type_payment_1 = await create_type_payment(name_for_user="name_2", index=1)
    type_payment_0 = await create_type_payment(name_for_user="name_1", index=0)
    type_payment_2 = await create_type_payment(name_for_user="name_1", index=2)

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
async def test_filling_sold_account_only_one(create_type_payment):
    type_payment_1 = await create_type_payment(name_for_user="name_1")

    await filling.filling_types_payments_by_id(type_payment_1.type_payment_id)

    async with get_redis() as session_redis:
        value = await session_redis.get(f"type_payments:{type_payment_1.type_payment_id}")
        assert value
        type_payment = orjson.loads(value)

    assert type_payment == type_payment_1.to_dict()
