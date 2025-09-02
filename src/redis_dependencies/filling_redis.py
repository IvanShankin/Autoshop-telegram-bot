import orjson


from typing import Type, Any, Optional, Callable

from datetime import datetime, timedelta, UTC

from sqlalchemy import select
from src.database.core_models import Users, BannedAccounts
from src.modules.admin_actions.models import Admins
from src.modules.discounts.models import PromoCodes, Vouchers
from src.modules.referrals.models import ReferralLevels
from src.modules.selling_accounts.models import TypeAccountServices, AccountServices, AccountCategories, \
    ProductAccounts, SoldAccounts
from src.redis_dependencies.core_redis import get_redis
from src.database.database import get_db, Base
from src.redis_dependencies.time_storage import TIME_USER, TIME_SOLD_ACCOUNTS_BY_OWNER, TIME_SOLD_ACCOUNTS_BY_ACCOUNT


async def filling_all_redis():
    """Заполняет redis необходимыми данными. Использовать только после заполнения БД"""
    await filling_referral_levels()
    await filling_users()
    await filling_admins()
    await filling_banned_accounts()
    await filling_type_account_services()
    await filling_account_services()
    await filling_account_categories_by_service_id()
    await filling_account_categories_by_category_id()
    await filling_product_accounts_by_category_id()
    await filling_product_accounts_by_account_id()
    await filling_sold_accounts_by_owner_id()
    await filling_sold_accounts_by_accounts_id()
    await filling_promo_code()
    await filling_vouchers()


async def _fill_redis_single_objects(
        model: Type,
        key_prefix: str,
        key_extractor: Callable[[Any], str],
        value_extractor: Callable[[Any], Any] = lambda x: orjson.dumps(x.to_dict()),
        field_condition: Optional[Any] = None,
        ttl: Optional[Callable[[Any], timedelta]] = None
):
    """

    Заполняет Redis одиночными объектами
    :param model: модель БД
    :param key_prefix: префикс у ключа redis ("key_prefix:other_data")
    :param field_condition: условие отбора. Пример: (User.user_id == 1)
    :param key_extractor: lambda функция для вызова второй части ключа. Пример: lambda user: user.user_id
    :param value_extractor: lambda функция для метода преобразования в json строку исходное значение. Пример:  lambda x: orjson.dumps(x.to_dict())
    :param key_extractor:
    :param value_extractor:
    :param ttl:
    """
    async with get_db() as session_db:
        if field_condition:
            result_db = await session_db.execute(select(model).where(field_condition))
        else:
            result_db = await session_db.execute(select(model))

        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for obj in result:
                        key = f"{key_prefix}:{key_extractor(obj)}" # формируется ключ
                        value = value_extractor(obj)

                        if ttl:
                            if ttl(obj): # если дата есть
                                ttl_in_seconds = int(ttl(obj).total_seconds())
                                if ttl_in_seconds > 1:
                                    await pipe.setex(key, ttl_in_seconds, value)
                            else: # если даты нет, то бессрочно
                                await pipe.set(key, value)

                        else:
                            await pipe.set(key, value)
                    await pipe.execute()

async def _fill_redis_grouped_objects(
        model: Type,
        group_by_field_models: str,
        group_by_model: Type,
        group_by_field_for_group_model: str,
        key_prefix: str,
        filter_condition: Optional[Any] = None,
        ttl: Optional[int] = None
):
    """
    Заполняет Redis сгруппированными объектами.
    :param model: Модель БД которая заполнит redis.
    :param group_by_model: Модель по которой будет происходить группировка.
    :param group_by_field_for_group_model: Столбец по которому будет отбираться group_by_model.
    :param group_by_field_models: Столбец по которому будет отбираться model.
    :param key_prefix: Префикс у ключа redis
    :param filter_condition: Фильтрация model. Пример: (User.user_id == 1)
    :param ttl:
    :return:
    """
    async with get_db() as session_db:
        # Получаем все ID для группировки
        result_db = await session_db.execute(select(getattr(group_by_model, group_by_field_for_group_model)))
        group_ids = result_db.scalars().all()

        for group_id in group_ids:
            # Строим запрос с условием
            query = select(model).where(getattr(model, group_by_field_models) == group_id)
            if filter_condition is not None:
                query = query.where(filter_condition)

            result_db = await session_db.execute(query)
            grouped_objects = result_db.scalars().all()

            if grouped_objects:
                async with get_redis() as session_redis:
                    list_for_redis = [obj.to_dict() for obj in grouped_objects]
                    key = f"{key_prefix}:{group_id}"
                    value = orjson.dumps(list_for_redis)

                    if ttl:
                        await session_redis.setex(key, ttl, value)
                    else:
                        await session_redis.set(key, value)


async def filling_referral_levels():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(ReferralLevels))
        referral_levels = result_db.scalars().all()

        if referral_levels:
            async with get_redis() as session_redis:
                list_for_redis = [referral.to_dict() for referral in referral_levels]
                await session_redis.set("referral_levels", orjson.dumps(list_for_redis))

async def filling_users():
    await _fill_redis_single_objects(
        model=Users,
        key_prefix='user',
        key_extractor=lambda user: user.user_id,
        ttl=lambda user: TIME_USER
    )


async def filling_admins():
    await _fill_redis_single_objects(
        model=Admins,
        key_prefix='admin',
        key_extractor=lambda admin: admin.user_id,
        value_extractor=lambda x: '_'
    )

async def filling_banned_accounts():
    await _fill_redis_single_objects(
        model=BannedAccounts,
        key_prefix='banned_account',
        key_extractor=lambda banned_accounts: banned_accounts.user_id,
        value_extractor=lambda x: '_'
    )

async def filling_type_account_services():
    await _fill_redis_single_objects(
        model=TypeAccountServices,
        key_prefix='type_account_service',
        key_extractor=lambda type_account_service: type_account_service.name,
    )

async def filling_account_services():
    await _fill_redis_single_objects(
        model=AccountServices,
        key_prefix='account_service',
        key_extractor=lambda account_service: account_service.type_account_service_id,
    )

async def filling_account_categories_by_service_id():
    await _fill_redis_grouped_objects(
        model=AccountCategories,
        group_by_field_models="account_service_id",
        group_by_model=AccountServices,
        group_by_field_for_group_model="account_service_id",
        key_prefix="account_categories_by_service_id"
    )

async def filling_account_categories_by_category_id():
    await _fill_redis_single_objects(
        model=AccountCategories,
        key_prefix='account_categories_by_category_id',
        key_extractor=lambda account_category: account_category.account_category_id,
    )


async def filling_product_accounts_by_category_id():
    await _fill_redis_grouped_objects(
        model=ProductAccounts,
        group_by_field_models="account_category_id",
        group_by_model=AccountCategories,
        group_by_field_for_group_model="account_category_id",
        key_prefix="product_accounts_by_category_id"
    )

async def filling_product_accounts_by_account_id():
    await _fill_redis_single_objects(
        model=ProductAccounts,
        key_prefix='product_accounts_by_account_id',
        key_extractor=lambda product_accounts_by_account_id: product_accounts_by_account_id.account_id,
    )


async def filling_sold_accounts_by_owner_id():
    await _fill_redis_grouped_objects(
        model=SoldAccounts,
        group_by_field_models='owner_id',
        group_by_model=Users,
        group_by_field_for_group_model="user_id",
        key_prefix="sold_accounts_by_owner_id",
        filter_condition=(SoldAccounts.is_deleted == False),
        ttl=TIME_SOLD_ACCOUNTS_BY_OWNER
    )


async def filling_sold_accounts_by_accounts_id():
    await _fill_redis_single_objects(
        model=SoldAccounts,
        key_prefix='sold_accounts_by_accounts_id',
        key_extractor=lambda sold_account: sold_account.sold_account_id,
        field_condition=(SoldAccounts.is_deleted == False),
        ttl=lambda x: TIME_SOLD_ACCOUNTS_BY_ACCOUNT
    )


async def filling_promo_code():
    await _fill_redis_single_objects(
        model=PromoCodes,
        key_prefix='promo_code',
        key_extractor=lambda promo_code: promo_code.activation_code,
        field_condition=(PromoCodes.is_valid == True),
        ttl=lambda promo_code: promo_code.expire_at - datetime.now(UTC) if promo_code.expire_at else None
    )


async def filling_vouchers():
    await _fill_redis_single_objects(
        model=Vouchers,
        key_prefix='vouchers',
        key_extractor=lambda vouchers: vouchers.activation_code,
        field_condition=(Vouchers.is_valid == True),
        ttl=lambda vouchers: vouchers.expire_at - datetime.now(UTC) if vouchers.expire_at else None
    )

