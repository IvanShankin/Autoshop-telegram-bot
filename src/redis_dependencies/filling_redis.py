from datetime import datetime, timedelta, UTC
from typing import Type, Any, Optional, Callable, Iterable, Union, List

import orjson
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from src.config import ALLOWED_LANGS
from src.database.core_models import Users, BannedAccounts
from src.database.database import get_db
from src.modules.admin_actions.models import Admins
from src.modules.discounts.models import PromoCodes, Vouchers
from src.modules.referrals.database.models import ReferralLevels
from src.modules.selling_accounts.models import TypeAccountServices, AccountServices, AccountCategories, \
    ProductAccounts, SoldAccounts
from src.redis_dependencies.core_redis import get_redis
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

async def _fill_redis_single_objects_multilang(
    model: Type,
    key_prefix: str,
    key_extractor: Callable[[Any], str],
    *,
    field_condition: Optional[Any] = None,
    ttl_seconds: Optional[int] = None,
    joinedload_rels: Optional[Iterable[str]] = ("translations",),
):
    """
    Для каждой записи model кладём в redis по ключу:
      {key_prefix}:{key_extractor(obj)}:{lang}
    Только для тех lang, которые реально есть в obj.translations и которые входят в ALLOWED_LANGS.

    :param ttl_seconds: если None — бессрочно, иначе int секунд для всех ключей.
    :param joinedload_rels: имена отношений, которые следует предварительно загрузить (обычно "translations").
    """
    async with get_db() as session_db:
        query = select(model)
        if field_condition is not None:
            query = query.where(field_condition)
        # joinedload для избежания N+1
        if joinedload_rels:
            for rel in joinedload_rels:
                query = query.options(selectinload(getattr(model, rel)))
        result = (await session_db.execute(query)).scalars().all()

        if not result:
            return

        async with get_redis() as r:
            async with r.pipeline(transaction=False) as pipe:
                for obj in result:
                    obj_id = key_extractor(obj)

                    # получаем все языки которые имеются у данного объекта (obj)
                    langs = []
                    for t in getattr(obj, "translations", []) or []: # получение у объекта model, его translations
                        lang = getattr(t, "lang", None)
                        if not lang:
                            continue
                        if lang not in ALLOWED_LANGS:
                            continue
                        if lang not in langs:
                            langs.append(lang)

                    if not langs:
                        # у объекта нет переводов — пропускаем
                        continue

                    for lang in langs:
                        try:
                            value_obj = obj.to_localized_dict(lang)
                        except Exception: # если по какой-то причине to_localized_dict упадёт — пропускаем этот язык
                            continue
                        if not value_obj:
                            continue

                        value_bytes = orjson.dumps(value_obj)
                        key = f"{key_prefix}:{obj_id}:{lang}"
                        if ttl_seconds and ttl_seconds > 1:
                            await pipe.setex(key, int(ttl_seconds), value_bytes)
                        elif ttl_seconds and ttl_seconds < 1:
                            continue
                        else:
                            await pipe.set(key, value_bytes)
                await pipe.execute()


async def _fill_redis_grouped_objects_multilang(
    model: Type,
    group_by_field_models: str,
    group_by_model: Type,
    group_by_field_for_group_model: str,
    key_prefix: str,
    *,
    filter_condition: Optional[Any] = None,
    ttl_seconds: Optional[int] = None,
    joinedload_rels: Optional[Iterable[str]] = ("translations",),
):
    """
    Для каждой группы (берём id из group_by_model.group_by_field_for_group_model) формируем
    ключи {key_prefix}:{group_id}:{lang} содержащие список локализованных dict'ов
    (каждый элемент получается через obj.to_localized_dict(lang)).
    Записываем только те lang, у которых есть хотя бы один объект с переводом.
    """
    async with get_db() as session_db:
        group_ids = (await session_db.execute(select(getattr(group_by_model, group_by_field_for_group_model)))).scalars().all()

        if not group_ids:
            return

        async with get_redis() as r:
            for group_id in group_ids:
                # получаем объекты группы
                q = select(model).where(getattr(model, group_by_field_models) == group_id)
                if filter_condition is not None:
                    q = q.where(filter_condition)
                if joinedload_rels:
                    for rel in joinedload_rels:
                        q = q.options(selectinload(getattr(model, rel)))
                objs = (await session_db.execute(q)).scalars().all()
                if not objs:
                    continue

                # union языков, которые реально есть среди объектов (и допустимы)
                langs_set = set()
                for obj in objs:
                    for t in getattr(obj, "translations", []) or []:
                        lang = getattr(t, "lang", None)
                        if lang and lang in ALLOWED_LANGS:
                            langs_set.add(lang)

                if not langs_set:
                    continue

                async with r.pipeline(transaction=False) as pipe:
                    for lang in langs_set:
                        list_for_redis = []
                        for obj in objs:
                            # если у объекта нет перевода для lang — пропускаем его
                            has_lang = False
                            for t in getattr(obj, "translations", []) or []:
                                if getattr(t, "lang", None) == lang:
                                    has_lang = True
                                    break
                            if not has_lang:
                                continue

                            try:
                                value_obj = obj.to_localized_dict(lang)
                            except Exception:
                                continue
                            if not value_obj:
                                continue
                            list_for_redis.append(value_obj)

                        if not list_for_redis:
                            continue

                        key = f"{key_prefix}:{group_id}:{lang}"
                        value_bytes = orjson.dumps(list_for_redis)
                        if ttl_seconds and ttl_seconds > 1:
                            await pipe.setex(key, int(ttl_seconds), value_bytes)
                        else:
                            await pipe.set(key, value_bytes)
                    await pipe.execute()

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
    await _fill_redis_grouped_objects_multilang(
        model=AccountCategories,
        group_by_field_models="account_service_id",
        group_by_model=AccountServices,
        group_by_field_for_group_model="account_service_id",
        key_prefix="account_categories_by_service_id",
        joinedload_rels=("translations",),
    )

async def filling_account_categories_by_category_id():
    await _fill_redis_single_objects_multilang(
        model=AccountCategories,
        key_prefix="account_categories_by_category_id",
        key_extractor= lambda account_category: account_category.account_category_id,
        joinedload_rels=("translations",)
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
    await _fill_redis_grouped_objects_multilang(
        model=SoldAccounts,
        group_by_field_models="owner_id",
        group_by_model=Users,
        group_by_field_for_group_model="user_id",
        key_prefix="sold_accounts_by_owner_id",
        filter_condition=(SoldAccounts.is_deleted == False),
        ttl_seconds=TIME_SOLD_ACCOUNTS_BY_OWNER.total_seconds(),
        joinedload_rels=("translations",),
    )


async def filling_sold_accounts_by_accounts_id():
    await _fill_redis_single_objects_multilang(
        model=SoldAccounts,
        key_prefix="sold_accounts_by_accounts_id",
        key_extractor=lambda s: s.sold_account_id,
        field_condition=(SoldAccounts.is_deleted == False),
        joinedload_rels=("translations",),
        ttl_seconds=TIME_SOLD_ACCOUNTS_BY_ACCOUNT.total_seconds(),  # или время в секундах
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

