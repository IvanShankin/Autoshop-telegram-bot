from datetime import datetime, timedelta, UTC
from typing import Type, Any, Optional, Callable, Iterable, List

import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import distinct

from src.config import ALLOWED_LANGS
from src.services.database.discounts.models import SmallVoucher
from src.services.database.selling_accounts.models.models import AccountStorage
from src.services.database.selling_accounts.models.schemas import SoldAccountFull, SoldAccountSmall, \
    AccountStoragePydentic, ProductAccountFull, AccountCategoryFull
from src.services.database.selling_accounts.models import TypeAccountServices, AccountServices, AccountCategories, \
    ProductAccounts, SoldAccounts
from src.services.database.system.models import UiImages
from src.services.database.users.models import Users, BannedAccounts
from src.services.database.system.models import Settings, TypePayments
from src.services.database.core.database import get_db
from src.services.database.admins.models import Admins
from src.services.database.discounts.models import PromoCodes, Vouchers
from src.services.database.referrals.models import ReferralLevels
from src.services.redis.core_redis import get_redis
from src.services.redis.time_storage import TIME_USER, TIME_SOLD_ACCOUNTS_BY_OWNER, TIME_SOLD_ACCOUNTS_BY_ACCOUNT, \
    TIME_ALL_VOUCHER
from src.utils.core_logger import logger


async def filling_all_redis():
    """Заполняет redis необходимыми данными. Использовать только после заполнения БД"""
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypePayments.type_payment_id))
        types_payments_ids: List[int] = result_db.scalars().all()
        for type_id in types_payments_ids:
            await filling_types_payments_by_id(type_id)

        result_db = await session_db.execute(select(UiImages))
        ui_images: List[UiImages] = result_db.scalars().all()
        for ui_image in ui_images:
            await filling_ui_image(ui_image.key)

        result_db = await session_db.execute(select(Users.user_id))
        users_ids: List[int] = result_db.scalars().all()
        for user_id in users_ids:
            await filling_voucher_by_user_id(user_id)

        result_db = await session_db.execute(select(ProductAccounts.account_id))
        product_accounts_ids: List[int] = result_db.scalars().all()
        for product_account_id in product_accounts_ids:
            await filling_product_account_by_account_id(product_account_id)

        result_db = await session_db.execute(select(distinct(SoldAccounts.owner_id)))
        union_sold_accounts_owner_ids: List[int] = result_db.scalars().all()
        for owner_id in union_sold_accounts_owner_ids:
            await filling_sold_accounts_by_owner_id(owner_id)

        result_db = await session_db.execute(select(SoldAccounts.sold_account_id))
        sold_accounts_ids: List[int] = result_db.scalars().all()
        for account_id in sold_accounts_ids:
            await filling_sold_account_by_account_id(account_id)

    await filling_settings()
    await filling_referral_levels()
    await filling_all_types_payments()
    await filling_users()
    await filling_admins()
    await filling_banned_accounts()
    await filling_all_types_account_service()
    await filling_type_account_services()
    await filling_all_account_services()
    await filling_account_services()
    await filling_account_categories_by_service_id()
    await filling_account_categories_by_category_id()
    await filling_product_accounts_by_category_id()
    await filling_promo_code()
    await filling_vouchers()
    logger.info("Redis filling successfully")


async def _delete_keys_by_pattern(pattern: str):
    """Удаляет все ключи, соответствующие шаблону. Пример: 'user:*'"""
    count = 0
    async with get_redis() as session_redis:
        async for key in session_redis.scan_iter(match=pattern):
            await session_redis.delete(key)
            count += 1
    return count


async def _fill_redis_single_objects(
        model: Type,
        key_prefix: str,
        key_extractor: Callable[[Any], str],
        value_extractor: Callable[[Any], Any] = lambda x: orjson.dumps(x.to_dict()),
        field_condition: Optional[Any] = None,
        ttl: Optional[Callable[[Any], timedelta]] = None
):
    """
    Заполняет Redis одиночными объектами. Если объекты в БД не будут найдены, то ничего не заполнит
    :param model: модель БД
    :param key_prefix: префикс у ключа redis ("key_prefix:other_data")
    :param field_condition: условие отбора. Пример: (User.user_id == 1)
    :param key_extractor: lambda функция для вызова второй части ключа. Пример: lambda user: user.user_id
    :param value_extractor: lambda функция для метода преобразования в json строку исходное значение. Пример:  lambda x: orjson.dumps(x.to_dict())
    :param key_extractor:
    :param value_extractor:
    :param ttl:
    """
    await _delete_keys_by_pattern(f'{key_prefix}:*')
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


async def filling_settings():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(Settings))
        settings = result_db.scalars().first()

        if settings:
            async with get_redis() as session_redis:
                await session_redis.set("settings", orjson.dumps(settings.to_dict()))

async def filling_ui_image(key: str):
    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages).where(UiImages.key == key))
        ui_image = result_db.scalar_one_or_none()

        if ui_image:
            async with get_redis() as session_redis:
                await session_redis.set(f"ui_image:{ui_image.key}", value=orjson.dumps(ui_image.to_dict()))

async def filling_referral_levels():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(ReferralLevels))
        referral_levels = result_db.scalars().all()

        if referral_levels:
            async with get_redis() as session_redis:
                list_for_redis = [referral.to_dict() for referral in referral_levels]
                await session_redis.set("referral_levels", orjson.dumps(list_for_redis))


async def filling_all_types_payments():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypePayments).order_by(TypePayments.index.asc()))
        types_payments = result_db.scalars().all()

        # сохраним даже пустой список
        async with get_redis() as session_redis:
            list_for_redis = [type_pay.to_dict() for type_pay in types_payments]
            await session_redis.set("all_types_payments", orjson.dumps(list_for_redis))


async def filling_types_payments_by_id(type_payment_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypePayments).where(TypePayments.type_payment_id == type_payment_id))
        type_payment = result_db.scalar_one_or_none()

        async with get_redis() as session_redis:
            if type_payment:
                await session_redis.set(f'type_payments:{type_payment_id}', orjson.dumps(type_payment.to_dict()))
            else:
                await session_redis.delete(f'type_payments:{type_payment_id}')


async def filling_users():
    await _fill_redis_single_objects(
        model=Users,
        key_prefix='user',
        key_extractor=lambda user: user.user_id,
        ttl=lambda user: TIME_USER
    )


async def filling_user(user: Users):
    async with get_redis() as session_redis:
        await session_redis.setex(f"user:{user.user_id}", TIME_USER, orjson.dumps(user.to_dict()))


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
        value_extractor=lambda x: x.reason
    )


async def filling_all_types_account_service():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypeAccountServices))
        all_types_service: list[TypeAccountServices] = result_db.scalars().all()
        types_in_dicts = [service.to_dict() for service in all_types_service]

        async with get_redis() as session_redis:
            await session_redis.set("types_account_service", orjson.dumps(types_in_dicts))


async def filling_type_account_services():
    await _fill_redis_single_objects(
        model=TypeAccountServices,
        key_prefix='type_account_service',
        key_extractor=lambda type_account_service: type_account_service.type_account_service_id,
    )


async def filling_all_account_services():
    await _delete_keys_by_pattern(f'account_services')
    async with get_db() as session_db:
        result_db = await session_db.execute(select(AccountServices).order_by(AccountServices.index.asc()))
        services = result_db.scalars().all()

    if services:
        list_service = [service.to_dict() for service in services]
        async with get_redis() as session_redis:
            await session_redis.set("account_services", orjson.dumps(list_service))


async def filling_account_services():
    await _fill_redis_single_objects(
        model=AccountServices,
        key_prefix='account_service',
        key_extractor=lambda account_service: account_service.account_service_id,
    )


async def filling_account_categories_by_service_id():
    await _delete_keys_by_pattern(f'account_categories_by_service_id:*')
    async with get_db() as session_db:
        service_ids = (await session_db.execute(select(AccountServices.account_service_id))).scalars().all()

        if not service_ids:
            return

        async with get_redis() as r:
            for service_id in service_ids:
                # получаем объекты группы
                result_db = await session_db.execute(
                    select(AccountCategories)
                    .where(AccountCategories.account_service_id == service_id)
                    .order_by(AccountCategories.index.asc())
                    .options(selectinload(AccountCategories.translations), selectinload(AccountCategories.product_accounts))
                )

                account_categories: list[AccountCategories] = result_db.scalars().all()
                if not account_categories:
                    continue

                # union языков, которые реально есть среди объектов (и допустимы)
                langs_set = set()
                for category in account_categories:
                    for translate in category.translations:
                        lang = translate.lang
                        if lang and lang in ALLOWED_LANGS:
                            langs_set.add(lang)

                if not langs_set:
                    continue

                async with r.pipeline(transaction=False) as pipe:
                    for lang in langs_set:
                        list_for_redis = []
                        for category in account_categories:
                            # если у объекта нет перевода для lang — пропускаем его
                            has_lang = False
                            for translate in category.translations:
                                if translate.lang == lang:
                                    has_lang = True
                                    break
                            if not has_lang:
                                continue

                            result_category = AccountCategoryFull.from_orm_with_translation(
                                category = category,
                                quantity_product_account = len(category.product_accounts),
                                lang = lang
                            )

                            list_for_redis.append(result_category.model_dump())

                        if not list_for_redis:
                            continue

                        key = f"account_categories_by_service_id:{service_id}:{lang}"
                        value_bytes = orjson.dumps(list_for_redis)
                        await pipe.set(key, value_bytes)
                    await pipe.execute()


async def filling_account_categories_by_category_id():
    await _delete_keys_by_pattern(f'account_categories_by_category_id:*') # удаляем по каждой категории
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountCategories)
            .options(selectinload(AccountCategories.translations), selectinload(AccountCategories.product_accounts))
        )
        categories: list[AccountCategories] = result_db.scalars().all()

        if not categories:
            return

        async with get_redis() as session_redis:
            async with session_redis.pipeline(transaction=False) as pipe:
                for category in categories:
                    category_id = category.account_category_id

                    # получаем все языки которые имеются у данного объекта (obj)
                    langs = []
                    for translate in category.translations:  # получение у объекта model, его translations
                        lang = translate.lang
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
                            value_obj = AccountCategoryFull.from_orm_with_translation(
                                category=category,
                                quantity_product_account=len(category.product_accounts),
                                lang=lang
                            )
                        except Exception:  # если по какой-то причине to_localized_dict упадёт — пропускаем этот язык
                            continue
                        if not value_obj:
                            continue

                        value_bytes = orjson.dumps(value_obj.model_dump())
                        key = f"account_categories_by_category_id:{category_id}:{lang}"
                        await pipe.set(key, value_bytes)
                await pipe.execute()


async def filling_product_accounts_by_category_id():
    await _delete_keys_by_pattern(f'product_accounts_by_category_id:*') # удаляем по каждой категории
    async with get_db() as session_db:
        # Получаем все ID для группировки
        result_db = await session_db.execute(select(ProductAccounts.account_category_id))
        category_ids = result_db.scalars().all()

        for category_id in category_ids:
            # Строим запрос с условием
            result_db = await session_db.execute(select(ProductAccounts).where(ProductAccounts.account_category_id == category_id))
            product_accounts = result_db.scalars().all()

            if product_accounts:
                async with get_redis() as session_redis:
                    list_for_redis = [obj.to_dict() for obj in product_accounts]
                    key = f"product_accounts_by_category_id:{category_id}"
                    value = orjson.dumps(list_for_redis)
                    await session_redis.set(key, value)



async def filling_product_account_by_account_id(account_id: int):
    await _delete_keys_by_pattern(f'product_accounts_by_account_id:{account_id}') # удаляем только по данному id
    async with get_db() as session_db:
        result_db = await session_db.execute(select(ProductAccounts).where(ProductAccounts.account_id == account_id))
        account: ProductAccounts = result_db.scalar_one_or_none()
        if not account: return

        result_db = await session_db.execute(select(AccountStorage).where(AccountStorage.account_storage_id == account.account_storage_id))
        storage_account: AccountStorage = result_db.scalar_one_or_none()
        if not storage_account: return

        async with get_redis() as session_redis:
            product_account = ProductAccountFull(
                account_id = account.account_id,
                type_account_service_id = account.type_account_service_id,
                account_category_id = account.account_category_id,
                created_at = account.created_at,
                account_storage = AccountStoragePydentic(**storage_account.to_dict())
            )
            await session_redis.set(
                f'product_accounts_by_account_id:{account.account_id}',
                orjson.dumps(product_account.model_dump())
            )


async def filling_sold_accounts_by_owner_id(owner_id: int):
    """Заполнит SoldAccounts по всем языкам которые есть"""
    await _delete_keys_by_pattern(f'sold_accounts_by_owner_id:{owner_id}:*') # удаляем по всем аккаунтах у владельца
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(SoldAccounts)
            .join(SoldAccounts.account_storage)  # связываем таблицы
            .options(selectinload(SoldAccounts.translations), selectinload(SoldAccounts.account_storage))
            .where(
                (SoldAccounts.owner_id == owner_id) &
                (SoldAccounts.account_storage.has(is_active=True))  # фильтр по связанной модели
            )
            .order_by(SoldAccounts.sold_at.desc())
        )
        accounts_list = result_db.scalars().all()

        # все языки
        languages = {
            t.lang
            for account in accounts_list
            for t in account.translations
        }

        # хранит все списки с аккаунтами на разных языках. [[список с аккаунтами на одном языке, код языка]]
        list_accounts_by_lang: list[tuple[list, str]] = []

        for lang in languages:
            new_list_accounts = []
            for account in accounts_list:
                account_full = SoldAccountSmall.from_orm_with_translation(account, lang=lang)
                new_list_accounts.append(account_full.model_dump())
            list_accounts_by_lang.append((new_list_accounts, lang))

    async with get_redis() as session_redis:
        for account_list, lang in list_accounts_by_lang:
            await session_redis.setex(
                f"sold_accounts_by_owner_id:{owner_id}:{lang}",
                TIME_SOLD_ACCOUNTS_BY_OWNER,
                orjson.dumps(account_list)
            )


async def filling_sold_account_by_account_id(sold_account_id: int):
    """Заполнит SoldAccounts по всем языкам которые есть"""
    await _delete_keys_by_pattern(f'sold_accounts_by_accounts_id:{sold_account_id}:*') # удаляем по всем языкам
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(SoldAccounts)
            .join(SoldAccounts.account_storage)  # связываем таблицы
            .options(selectinload(SoldAccounts.translations), selectinload(SoldAccounts.account_storage))
            .where(
                (SoldAccounts.sold_account_id == sold_account_id) &
                (SoldAccounts.account_storage.has(is_active=True))  # фильтр по связанной модели
            )
        )
        account = result_db.scalar_one_or_none()

        if account:
            # все языки
            languages = {t.lang for t in account.translations}

            # хранит все списки с аккаунтами на разных языках. [[список с аккаунтами на одном языке, код языка]]
            list_accounts_by_lang: list[tuple[SoldAccountFull, str]] = []

            for lang in languages:
                account_full = await SoldAccountFull.from_orm_with_translation(account, lang=lang)
                list_accounts_by_lang.append((account_full, lang))

            async with get_redis() as session_redis:
                for account, lang in list_accounts_by_lang:
                    await session_redis.setex(
                        f"sold_accounts_by_accounts_id:{sold_account_id}:{lang}",
                        TIME_SOLD_ACCOUNTS_BY_ACCOUNT,
                        orjson.dumps(account.model_dump())
                    )


async def filling_promo_code():
    await _fill_redis_single_objects(
        model=PromoCodes,
        key_prefix='promo_code',
        key_extractor=lambda promo_code: promo_code.activation_code,
        field_condition=(PromoCodes.is_valid == True),
        ttl=lambda promo_code: promo_code.expire_at - datetime.now(UTC) if promo_code.expire_at else None
    )


async def filling_voucher_by_user_id(user_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Vouchers)
            .where(
                (Vouchers.creator_id == user_id) &
                (Vouchers.is_valid == True) &
                (Vouchers.is_created_admin == False)
            ).order_by(Vouchers.start_at.desc())
        )
        vouchers = result_db.scalars().all()

    async with get_redis() as session_redis:
        result_list = [ SmallVoucher.from_orm_model(voucher).model_dump() for voucher in vouchers ]
        await session_redis.delete(f'voucher_by_user:{user_id}')
        await session_redis.setex(f'voucher_by_user:{user_id}', TIME_ALL_VOUCHER, orjson.dumps(result_list))


async def filling_vouchers():
    await _fill_redis_single_objects(
        model=Vouchers,
        key_prefix='voucher',
        key_extractor=lambda vouchers: vouchers.activation_code,
        field_condition=(Vouchers.is_valid == True),
        ttl=lambda vouchers: vouchers.expire_at - datetime.now(UTC) if vouchers.expire_at else None
    )

