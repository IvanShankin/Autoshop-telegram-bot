import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config import get_config
from src.services.database.categories.models import ProductUniversal
from src.services.database.categories.models.product_universal import UniversalStorage, SoldUniversal
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull, \
    SoldUniversalSmall, SoldUniversalFull
from src.services.database.core import get_db
from src.services.redis.core_redis import get_redis
from src.services.redis.filling.helpers_func import _delete_keys_by_pattern, _filling_product_by_category_id, \
    filling_sold_products_by_owner_id, filling_sold_entity_by_id
from src.services.redis.time_storage import TIME_SOLD_UNIVERSAL_PRODUCT_BY_OWNER, TIME_SOLD_UNIVERSAL_PRODUCT_BY_PRODUCT


async def filling_product_universal_by_category():
    await _filling_product_by_category_id(ProductUniversal, "product_universal_by_category")


async def filling_universal_by_product_id(product_universal_id: int):
    await _delete_keys_by_pattern(f'product_universal:{product_universal_id}')  # удаляем только по данному id

    async with get_db() as session_db:
        result = await session_db.execute(
            select(ProductUniversal)
            .options(
                selectinload(ProductUniversal.storage)
                .selectinload(UniversalStorage.translations)
            )
            .where(ProductUniversal.product_universal_id == product_universal_id)
        )

        product: ProductUniversal | None = result.scalar_one_or_none()
        if not product:
            return

        async with get_redis() as session_redis:
            product_result = ProductUniversalFull.from_orm_model(
                product_universal=product,
                language=get_config().app.default_lang
            )
            await session_redis.set(
                f'product_universal:{product.product_universal_id}',
                orjson.dumps(product_result.model_dump())
            )


async def filling_sold_universal_by_owner_id(owner_id: int):
    await filling_sold_products_by_owner_id(
        model_db=SoldUniversal,
        owner_id=owner_id,
        key_prefix="sold_universal_by_owner_id",
        ttl=TIME_SOLD_UNIVERSAL_PRODUCT_BY_OWNER,
        options=(
            selectinload(SoldUniversal.storage)
            .selectinload(UniversalStorage.translations),
        ),
        filter_expr=(
            (SoldUniversal.owner_id == owner_id) &
            (SoldUniversal.storage.has(is_active=True))
        ),
        get_translations=lambda obj: obj.storage.translations,
        dto_factory=lambda obj, lang: SoldUniversalSmall.from_orm_model(obj, lang),
    )


async def filling_sold_universal_by_universal_id(sold_universal_id: int):
    await filling_sold_entity_by_id(
        model_db=SoldUniversal,
        entity_id=sold_universal_id,
        key_prefix="sold_universal",
        ttl=TIME_SOLD_UNIVERSAL_PRODUCT_BY_PRODUCT,
        options=(
            selectinload(SoldUniversal.storage)
            .selectinload(UniversalStorage.translations),
        ),
        filter_expr=(
            (SoldUniversal.sold_universal_id == sold_universal_id) &
            (SoldUniversal.storage.has(is_active=True))
        ),
        get_languages=lambda obj: (t.lang for t in obj.storage.translations),
        dto_factory=lambda obj, lang: SoldUniversalFull.from_orm_model(obj, language=lang),
    )


