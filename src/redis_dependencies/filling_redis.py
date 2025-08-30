import orjson

from datetime import datetime, UTC

from asyncpg.pgproto.pgproto import timedelta
from sqlalchemy import select
from src.database import Users, BannedAccounts
from src.modules.admin_actions.models import Admins
from src.modules.discounts.models import PromoCodes, Vouchers
from src.modules.selling_accounts.models import TypeAccountServices, AccountServices, AccountCategories, \
    ProductAccounts, SoldAccounts
from src.redis_dependencies.core_redis import get_redis
from src.database.database import get_db
from src.redis_dependencies.time_storage import TIME_USER, TIME_SOLD_ACCOUNTS_BY_OWNER, TIME_SOLD_ACCOUNTS_BY_ACCOUNT


async def filling_all_redis():
    """Заполняет redis необходимыми данными. Использовать только после заполнения БД"""
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




async def filling_users():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for user in result:
                        await pipe.setex(f"user:{user.user_id}", TIME_USER, orjson.dumps(user.to_dict()))
                    await pipe.execute() # выполняем пачкой

async def filling_admins():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(Admins))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for admin in result:
                        await pipe.set(f"admin:{admin.user_id}", '_')
                    await pipe.execute()

async def filling_banned_accounts():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(BannedAccounts))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for banned_accounts in result:
                        await pipe.set(f"banned_account:{banned_accounts.user_id}", '_')
                    await pipe.execute()

async def filling_type_account_services():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(TypeAccountServices))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for type_account_service in result:
                        await pipe.set(
                            f"type_account_service:{type_account_service.name}",
                            orjson.dumps(type_account_service.to_dict())
                        )
                    await pipe.execute()

async def filling_account_services():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(AccountServices))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for account_service in result:
                        await pipe.set(
                            f"account_service:{account_service.type_account_service_id}",
                            orjson.dumps(account_service.to_dict())
                        )
                    await pipe.execute()

async def filling_account_categories_by_service_id():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(AccountServices.account_service_id))
        result_account_service_ids = result_db.scalars().all()

        for account_service_id in result_account_service_ids:
            result_db = await session_db.execute(
                select(AccountCategories)
                .where(AccountCategories.account_service_id == account_service_id)
            )
            result_account_categories = result_db.scalars().all()

            if result_account_categories:
                async with get_redis() as session_redis:
                    list_for_redis = []
                    for account_category in result_account_categories:
                        list_for_redis.append(account_category.to_dict())

                    await session_redis.set(
                        f"account_categories_by_service_id:{account_service_id}",
                        orjson.dumps(list_for_redis)
                    )

async def filling_account_categories_by_category_id():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(AccountCategories))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for account_category in result:
                        await pipe.set(
                            f"account_categories_by_category_id:{account_category.account_category_id}",
                            orjson.dumps(account_category.to_dict())
                        )
                    await pipe.execute()


async def filling_product_accounts_by_category_id():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(AccountCategories.account_category_id))
        result_account_category_ids = result_db.scalars().all()

        for account_category_id in result_account_category_ids:
            result_db = await session_db.execute(
                select(ProductAccounts)
                .where(ProductAccounts.account_category_id == account_category_id)
            )
            result_product_account = result_db.scalars().all()

            if result_product_account:
                async with get_redis() as session_redis:
                    list_for_redis = []
                    for product_account in result_product_account:
                        list_for_redis.append(product_account.to_dict())

                    await session_redis.set(
                        f"product_accounts_by_category_id:{account_category_id}",
                        orjson.dumps(list_for_redis)
                    )

async def filling_product_accounts_by_account_id():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(ProductAccounts))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for product_account in result:
                        await pipe.set(
                            f"product_accounts_by_account_id:{product_account.account_id}",
                            orjson.dumps(product_account.to_dict())
                        )
                    await pipe.execute()


async def filling_sold_accounts_by_owner_id():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users.user_id))
        result_users_ids = result_db.scalars().all()

        for user_id in result_users_ids:
            result_db = await session_db.execute(
                select(SoldAccounts)
                .where((SoldAccounts.owner_id == user_id) & (SoldAccounts.is_deleted == False))
            )
            result_sold_accounts = result_db.scalars().all()

            if result_sold_accounts:
                async with get_redis() as session_redis:
                    list_for_redis = []
                    for sold_account in result_sold_accounts:
                        list_for_redis.append(sold_account.to_dict())

                    await session_redis.setex(
                        f"sold_accounts_by_owner_id:{user_id}",
                        TIME_SOLD_ACCOUNTS_BY_OWNER,
                        orjson.dumps(list_for_redis)
                    )


async def filling_sold_accounts_by_accounts_id():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(SoldAccounts).where(SoldAccounts.is_deleted == False))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for sold_account in result:
                        await pipe.setex(
                            f"sold_accounts_by_accounts_id:{sold_account.account_id}",
                            TIME_SOLD_ACCOUNTS_BY_ACCOUNT,
                            orjson.dumps(sold_account.to_dict())
                        )
                    await pipe.execute()


async def filling_promo_code():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(PromoCodes).where(PromoCodes.is_valid == True))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for promo_code in result:
                        time_life: timedelta = promo_code.expire_at - datetime.now(UTC)

                        await pipe.setex(
                            f"promo_code:{promo_code.activation_code}",
                            time_life, # на время жизни
                            orjson.dumps(promo_code.to_dict())
                        )
                    await pipe.execute()


async def filling_vouchers():
    async with get_db() as session_db:
        result_db = await session_db.execute(select(Vouchers).where(Vouchers.is_valid == True))
        result = result_db.scalars().all()

        if result:
            async with get_redis() as session_redis:
                async with session_redis.pipeline(transaction=False) as pipe:
                    for vouchers in result:
                        time_life: timedelta = vouchers.expire_at - datetime.now(UTC)

                        await pipe.setex(
                            f"vouchers:{vouchers.activation_code}",
                            time_life, # на время жизни
                            orjson.dumps(vouchers.to_dict())
                        )
                    await pipe.execute()
