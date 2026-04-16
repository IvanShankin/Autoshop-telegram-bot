import pytest

from src.containers import RequestContainer


async def _create_main_branch(
    create_category,
    create_product_account,
    *,
    root_name: str,
    child_name: str,
    root_index: int
):
    root = await create_category(
        filling_redis=False,
        name=root_name,
        index=root_index,
    )
    child = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name=child_name,
        index=0,
    )
    await create_product_account(
        filling_redis=False,
        category_id=child.category_id,
    )
    return root, child


@pytest.mark.asyncio
async def test_fill_main_categories_populates_sorted_cache(
    container_fix,
    create_category,
    create_product_account,
):
    root_1, _ = await _create_main_branch(
        create_category,
        create_product_account,
        root_name="main-1",
        child_name="main-1-storage",
        root_index=1,
    )
    root_2, _ = await _create_main_branch(
        create_category,
        create_product_account,
        root_name="main-2",
        child_name="main-2-storage",
        root_index=0,
    )

    await container_fix.categories_cache_filler_service.fill_main_categories()

    cached = await container_fix.categories_cache_repo.get_main_categories("ru")
    assert [item.category_id for item in cached] == [root_2.category_id, root_1.category_id]


@pytest.mark.asyncio
async def test_fill_category_by_parent_populates_child_cache(
    container_fix,
    create_category,
    create_product_account,
):
    root = await create_category(filling_redis=False, name="parent-root")
    child_1 = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name="child-1",
        index=1,
    )
    child_2 = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name="child-2",
        index=0,
    )
    await create_product_account(filling_redis=False, category_id=child_1.category_id)
    await create_product_account(filling_redis=False, category_id=child_2.category_id)

    await container_fix.categories_cache_filler_service.fill_category_by_parent(root.category_id)

    cached = await container_fix.categories_cache_repo.get_categories_by_parent(root.category_id, "ru")
    assert [item.category_id for item in cached] == [child_2.category_id, child_1.category_id]
    assert cached[0].quantity_product == 1
    assert cached[1].quantity_product == 1


@pytest.mark.asyncio
async def test_fill_category_by_id_populates_single_cache(
    container_fix,
    create_category,
    create_product_account,
):
    category = await create_category(
        filling_redis=False,
        name="single-storage",
        is_product_storage=True,
    )
    await create_product_account(
        filling_redis=False,
        category_id=category.category_id,
    )

    await container_fix.categories_cache_filler_service.fill_category_by_id(category.category_id)

    cached = await container_fix.categories_cache_repo.get_category(category.category_id, "ru")
    assert cached is not None
    assert cached.category_id == category.category_id
    assert cached.quantity_product == 1


@pytest.mark.asyncio
async def test_fill_need_category_handles_list_and_populates_related_cache(
    container_fix,
    create_category,
    create_product_account,
):
    root = await create_category(filling_redis=False, name="need-root")
    child = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name="need-child",
    )
    await create_product_account(filling_redis=False, category_id=child.category_id)

    await container_fix.categories_cache_filler_service.fill_need_category(
        categories_ids=[root.category_id, child.category_id]
    )

    cached_main = await container_fix.categories_cache_repo.get_main_categories("ru")
    cached_children = await container_fix.categories_cache_repo.get_categories_by_parent(root.category_id, "ru")
    cached_root = await container_fix.categories_cache_repo.get_category(root.category_id, "ru")
    cached_child = await container_fix.categories_cache_repo.get_category(child.category_id, "ru")

    assert [item.category_id for item in cached_main] == [root.category_id]
    assert [item.category_id for item in cached_children] == [child.category_id]
    assert cached_root is not None
    assert cached_child is not None


@pytest.mark.asyncio
async def test_fill_need_category_accepts_single_id(
    container_fix,
    create_category,
    create_product_account,
):
    root = await create_category(filling_redis=False, name="single-root")
    child = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name="single-child",
    )
    await create_product_account(filling_redis=False, category_id=child.category_id)

    await container_fix.categories_cache_filler_service.fill_need_category(root.category_id)

    cached_main = await container_fix.categories_cache_repo.get_main_categories("ru")
    cached_root = await container_fix.categories_cache_repo.get_category(root.category_id, "ru")

    assert [item.category_id for item in cached_main] == [root.category_id]
    assert cached_root is not None


@pytest.mark.asyncio
async def test_fill_need_category_requires_input(container_fix):
    with pytest.raises(ValueError):
        await container_fix.categories_cache_filler_service.fill_need_category()
