import pytest
from sqlalchemy import select

from src.database.models.categories import Categories, CategoryTranslation
from src.exceptions import AccountCategoryNotFound, CategoryStoresSubcategories, IncorrectedNumberButton, TheCategoryStorageAccount
from src.exceptions.business import NotEnoughArguments
from src.models.create_models.category import CreateCategory
from src.models.update_models.category import UpdateCategory


async def _create_main_with_storage_child(
    container_fix,
    create_category,
    create_product_account,
    *,
    root_name: str,
    root_index: int,
    child_name: str,
    child_index: int,
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
        index=child_index,
    )
    await create_product_account(
        filling_redis=False,
        category_id=child.category_id,
    )
    return root, child


@pytest.mark.asyncio
async def test_has_accounts_in_subtree_and_filter_categories(
    container_fix,
    create_category,
    create_product_account,
):
    root = await create_category(filling_redis=False, name="root")
    hidden_child = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        show=False,
        name="hidden-child",
    )
    grand = await create_category(
        filling_redis=False,
        parent_id=hidden_child.category_id,
        is_product_storage=True,
        name="grand",
    )
    await create_product_account(filling_redis=False, category_id=grand.category_id)
    grand = grand.model_copy(update={"quantity_product": 1})

    all_categories = [root, hidden_child, grand]
    assert container_fix.category_service._has_accounts_in_subtree(grand, all_categories) is True
    assert container_fix.category_service._has_accounts_in_subtree(hidden_child, all_categories) is False
    assert container_fix.category_service._has_accounts_in_subtree(root, all_categories) is False

    filtered = container_fix.category_service._filter_categories([root, hidden_child, grand])
    assert [item.category_id for item in filtered] == [grand.category_id]


@pytest.mark.asyncio
async def test_create_category_persists_and_populates_cache(
    container_fix,
    session_db_fix,
):
    dto = CreateCategory(
        language="ru",
        name="created-category",
        description="created-description",
        number_buttons_in_row=2,
    )

    created = await container_fix.category_service.create_category(dto)

    result = await session_db_fix.execute(
        select(Categories).where(Categories.category_id == created.category_id)
    )
    db_category = result.scalar_one()
    assert db_category.category_id == created.category_id

    result_translate = await session_db_fix.execute(
        select(CategoryTranslation).where(CategoryTranslation.category_id == created.category_id)
    )
    assert result_translate.scalar_one_or_none() is not None

    cached = await container_fix.categories_cache_repo.get_category(created.category_id, "ru")
    assert cached is not None
    assert cached.name == "created-category"
    assert created.number_buttons_in_row == 2


@pytest.mark.asyncio
async def test_create_category_rejects_storage_parent(
    container_fix,
    create_category,
):
    parent = await create_category(
        filling_redis=False, is_product_storage=True, name="storage-parent"
    )

    with pytest.raises(TheCategoryStorageAccount):
        await container_fix.category_service.create_category(
            CreateCategory(
                language="ru",
                name="child",
                parent_id=parent.category_id,
            )
        )


@pytest.mark.asyncio
async def test_get_category_by_id_loads_from_db_and_caches(
    container_fix,
    create_category,
):
    category = await create_category(filling_redis=False, name="cached-source")

    assert await container_fix.categories_cache_repo.get_category(category.category_id, "ru") is None

    result = await container_fix.category_service.get_category_by_id(category.category_id)
    assert result is not None
    assert result.model_dump() == category.model_dump()

    cached = await container_fix.categories_cache_repo.get_category(category.category_id, "ru")
    assert cached is not None
    assert cached.model_dump() == category.model_dump()

    assert await container_fix.category_service.get_category_by_id(999999999) is None


@pytest.mark.asyncio
async def test_get_categories_for_main_categories_filters_and_sorts(
    container_fix,
    create_category,
    create_product_account,
):
    root_1 = await create_category(
        filling_redis=False,
        name="main-1",
        index=1,
        is_product_storage=True,
    )
    root_2 = await create_category(
        filling_redis=False,
        name="main-2",
        index=0,
        is_product_storage=True,
    )
    await create_product_account(filling_redis=False, category_id=root_1.category_id)
    await create_product_account(filling_redis=False, category_id=root_2.category_id)

    result = await container_fix.category_service.get_categories()
    assert [item.category_id for item in result] == [root_2.category_id, root_1.category_id]

    cached = await container_fix.categories_cache_repo.get_main_categories("ru")
    assert [item.category_id for item in cached] == [root_2.category_id, root_1.category_id]


@pytest.mark.asyncio
async def test_get_categories_for_children_filters_and_caches_parent_branch(
    container_fix,
    create_category,
    create_product_account,
):
    root = await create_category(filling_redis=False, name="parent-root")
    child_1 = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name="visible-1",
        index=2,
    )
    child_2 = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name="visible-2",
        index=0,
    )
    hidden = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        show=False,
        name="hidden",
        index=1,
    )
    await create_product_account(filling_redis=False, category_id=child_1.category_id)
    await create_product_account(filling_redis=False, category_id=child_2.category_id)

    result = await container_fix.category_service.get_categories(parent_id=root.category_id)
    assert [item.category_id for item in result] == [child_2.category_id, child_1.category_id]

    cached = await container_fix.categories_cache_repo.get_categories_by_parent(root.category_id, "ru")
    assert [item.category_id for item in cached] == [child_2.category_id, hidden.category_id, child_1.category_id]


@pytest.mark.asyncio
async def test_get_quantity_products_in_category_returns_zero_and_nonzero(
    container_fix,
    create_category,
    create_product_account,
):
    empty_category = await create_category(filling_redis=False, name="empty")
    storage_category = await create_category(
        filling_redis=False,
        name="storage",
        is_product_storage=True,
    )
    await create_product_account(filling_redis=False, category_id=storage_category.category_id)

    assert await container_fix.category_service.get_quantity_products_in_category(empty_category.category_id) == 0
    assert await container_fix.category_service.get_quantity_products_in_category(storage_category.category_id) == 1


@pytest.mark.asyncio
async def test_update_category_shifts_indexes_and_updates_fields(
    container_fix,
    create_category,
    create_product_account,
    session_db_fix,
):
    root = await create_category(filling_redis=False, name="update-root")
    child_1 = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name="child-1",
        index=0,
    )
    child_2 = await create_category(
        filling_redis=False,
        parent_id=root.category_id,
        is_product_storage=True,
        name="child-2",
        index=1,
    )
    await create_product_account(filling_redis=False, category_id=child_1.category_id)
    await create_product_account(filling_redis=False, category_id=child_2.category_id)

    await container_fix.category_service.update_category(
        child_1.category_id,
        UpdateCategory(
            index=1,
            price=777,
            show=False,
        ),
    )

    result = await container_fix.category_service.get_categories(parent_id=root.category_id, return_not_show=True)
    assert [item.category_id for item in result] == [child_2.category_id, child_1.category_id]
    assert result[1].price == 777
    assert result[1].show is False

    db_row = await session_db_fix.execute(
        select(Categories).where(Categories.category_id == child_1.category_id)
    )
    updated = db_row.scalar_one()
    assert updated.price == 777
    assert updated.show is False


@pytest.mark.asyncio
async def test_update_category_rejects_invalid_number_buttons(container_fix):
    with pytest.raises(IncorrectedNumberButton):
        await container_fix.category_service.update_category(
            1,
            UpdateCategory(number_buttons_in_row=9),
        )


@pytest.mark.asyncio
async def test_check_category_before_del_rejects_products(container_fix, create_category, create_product_account):
    category = await create_category(filling_redis=False, is_product_storage=True, name="storage")
    await create_product_account(filling_redis=False, category_id=category.category_id)

    with pytest.raises(TheCategoryStorageAccount):
        await container_fix.category_service.check_category_before_del(category.category_id)


@pytest.mark.asyncio
async def test_check_category_before_del_rejects_children(container_fix, create_category):
    category = await create_category(filling_redis=False, name="parent")
    await create_category(
        filling_redis=False,
        parent_id=category.category_id,
        name="child",
    )

    with pytest.raises(CategoryStoresSubcategories):
        await container_fix.category_service.check_category_before_del(category.category_id)


@pytest.mark.asyncio
async def test_delete_category_removes_rows_and_ui_image(
    container_fix,
    create_category,
    session_db_fix,
):
    category = await create_category(filling_redis=False, name="deletable")

    await container_fix.category_service.delete_category(category.category_id)

    result_category = await session_db_fix.execute(
        select(Categories).where(Categories.category_id == category.category_id)
    )
    assert result_category.scalar_one_or_none() is None

    result_translation = await session_db_fix.execute(
        select(CategoryTranslation).where(CategoryTranslation.category_id == category.category_id)
    )
    assert result_translation.scalar_one_or_none() is None

    assert await container_fix.ui_images_service.get_ui_image(category.ui_image_key) is None
