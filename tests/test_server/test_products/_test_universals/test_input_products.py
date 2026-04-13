import os.path
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database.models.categories import ProductUniversal
from src.database.models.categories import UniversalMediaType
from src.database import get_db
from src.application.products.universals._universals_products import generate_example_zip_for_import
from src.infrastructure.files._media_paths import create_path_universal_storage
from src.application.products.universals._input_products import input_universal_products


async def test_input_universal_products(create_category):
    cat = await create_category()

    # создаст необходимую структуру
    zip_path = generate_example_zip_for_import()

    await input_universal_products(
        path_to_archive=zip_path,
        media_type=UniversalMediaType.MIXED,
        category_id=cat.category_id,
    )

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(ProductUniversal)
            .options(selectinload(ProductUniversal.storage))
            .where(ProductUniversal.category_id == cat.category_id)
        )
        created_products: List[ProductUniversal] = result_db.scalars().all()

        assert len(created_products) == 2 # в генерации создаётся две записи

        for product in created_products:
            # должен быть файл
            path_file = create_path_universal_storage(
                status=product.storage.status,
                uuid=product.storage.storage_uuid,
            )
            assert os.path.isfile(path_file)

