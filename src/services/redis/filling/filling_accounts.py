import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.services.database.categories.models import AccountStorage
from src.services.database.categories.models import ProductAccounts, SoldAccounts
from src.services.database.categories.models.shemas.product_account_schem import SoldAccountFull, SoldAccountSmall, \
    ProductAccountFull
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis
from src.services.redis.filling.helpers_func import _delete_keys_by_pattern, _filling_product_by_category_id, \
    filling_sold_products_by_owner_id, filling_sold_entity_by_id
from src.services.redis.time_storage import TIME_SOLD_ACCOUNTS_BY_OWNER, TIME_SOLD_ACCOUNTS_BY_ACCOUNT


async def filling_product_accounts_by_category_id():
    await _filling_product_by_category_id(ProductAccounts, "product_accounts_by_category")


async def filling_product_account_by_account_id(account_id: int):
    await _delete_keys_by_pattern(f'product_account:{account_id}') # удаляем только по данному id
    async with get_db() as session_db:
        result_db = await session_db.execute(select(ProductAccounts).where(ProductAccounts.account_id == account_id))
        account: ProductAccounts = result_db.scalar_one_or_none()
        if not account: return

        result_db = await session_db.execute(select(AccountStorage).where(AccountStorage.account_storage_id == account.account_storage_id))
        storage_account: AccountStorage = result_db.scalar_one_or_none()
        if not storage_account: return

        async with get_redis() as session_redis:
            product_account = ProductAccountFull.from_orm_model(
                product_account=account,
                storage_account=storage_account
            )
            await session_redis.set(
                f'product_account:{account.account_id}',
                orjson.dumps(product_account.model_dump())
            )


async def filling_sold_accounts_by_owner_id(owner_id: int):
    await filling_sold_products_by_owner_id(
        model_db=SoldAccounts,
        owner_id=owner_id,
        key_prefix="sold_accounts_by_owner_id",
        ttl=TIME_SOLD_ACCOUNTS_BY_OWNER,
        options=(
            selectinload(SoldAccounts.translations),
            selectinload(SoldAccounts.account_storage),
        ),
        filter_expr=(
            (SoldAccounts.owner_id == owner_id) &
            (SoldAccounts.account_storage.has(is_active=True))
        ),
        get_translations=lambda obj: obj.translations,
        dto_factory=lambda obj, lang: SoldAccountSmall.from_orm_with_translation(obj, lang=lang),
    )



async def filling_sold_account_by_account_id(sold_account_id: int):
    await filling_sold_entity_by_id(
        model_db=SoldAccounts,
        entity_id=sold_account_id,
        key_prefix="sold_account",
        ttl=TIME_SOLD_ACCOUNTS_BY_ACCOUNT,
        options=(
            selectinload(SoldAccounts.translations),
            selectinload(SoldAccounts.account_storage),
        ),
        filter_expr=(
            (SoldAccounts.sold_account_id == sold_account_id) &
            (SoldAccounts.account_storage.has(is_active=True))
        ),
        get_languages=lambda obj: (t.lang for t in obj.translations),
        dto_factory=lambda obj, lang: SoldAccountFull.from_orm_with_translation(obj, lang=lang),
    )

