import os.path


async def test_upload_universal_products(create_category, create_product_universal):
    from src.services.products.universals.upload_products import upload_universal_products
    cat = await create_category()

    for i in range(10):
        await create_product_universal(category_id=cat.category_id)

    gen = upload_universal_products(cat)
    path = await anext(gen)

    assert os.path.isfile(path)