import pytest

from tests.helpers.helper_functions import comparison_models

@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_product_account_by_category_id(use_redis, create_category, create_product_account):
    from src.services.database.categories.actions import get_product_account_by_category_id

    category = await create_category()
    account_1, _ = await create_product_account(use_redis, category_id=category.category_id)
    account_2, _ = await create_product_account(use_redis, category_id=category.category_id)
    account_other, _ = await create_product_account(use_redis)

    list_account = await get_product_account_by_category_id(category.category_id)
    list_account = [account.to_dict() for account in list_account]

    assert len(list_account) == 2
    assert any(comparison_models(account_1, account) for account in list_account)
    assert any(comparison_models(account_2, account) for account in list_account)


@pytest.mark.asyncio
async def test_get_full_product_account_by_category_id(create_category, create_product_account):
    from src.services.database.categories.actions import get_product_account_by_category_id

    category = await create_category()
    _, account_1 = await create_product_account(category_id=category.category_id)
    _, account_2 = await create_product_account(category_id=category.category_id)
    _, account_other = await create_product_account()

    list_account = await get_product_account_by_category_id(category.category_id, get_full=True)
    list_account = [account.model_dump() for account in list_account]

    assert len(list_account) == 2
    assert any(comparison_models(account_1.model_dump(), account) for account in list_account)
    assert any(comparison_models(account_2.model_dump(), account) for account in list_account)


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_product_account_by_account_id(use_redis, create_category, create_product_account):
    from src.services.database.categories.actions import get_product_account_by_account_id
    category = await create_category()
    _, account = await create_product_account(use_redis, category_id=category.category_id)
    _, account_other = await create_product_account(use_redis)

    account_result = await get_product_account_by_account_id(account.account_id)
    assert account == account_result


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_accounts_by_owner_id(use_redis, create_new_user, create_sold_account):
    from src.services.database.categories.actions import get_sold_accounts_by_owner_id

    owner = await create_new_user()
    account_1, _ = await create_sold_account(use_redis, owner_id=owner.user_id)
    account_2, _ = await create_sold_account(use_redis, owner_id=owner.user_id)
    account_other, _ = await create_sold_account(use_redis)

    list_account = await get_sold_accounts_by_owner_id(owner.user_id, owner.language)
    list_account = [account.model_dump() for account in list_account]

    # должен быть отсортирован по возрастанию даты
    assert len(list_account) == 2
    assert account_2.model_dump() == list_account[0]
    assert account_1.model_dump() == list_account[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_account_by_page(use_redis, create_new_user, create_sold_account):
    from src.services.database.categories.actions import get_sold_account_by_page

    owner = await create_new_user()
    account_1, _ = await create_sold_account(use_redis, owner_id=owner.user_id)
    account_2, _ = await create_sold_account(use_redis, owner_id=owner.user_id)
    account_other, _ = await create_sold_account(use_redis)

    list_account = await get_sold_account_by_page(owner.user_id, account_1.type_account_service, 1, owner.language)
    list_account = [account.model_dump() for account in list_account]

    # должен быть отсортирован по возрастанию даты
    assert len(list_account) == 2
    assert account_2.model_dump() == list_account[0]
    assert account_1.model_dump() == list_account[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_accounts_by_account_id(use_redis, create_sold_account):
    from src.services.database.categories.actions import get_sold_accounts_by_account_id

    _, account = await create_sold_account(use_redis)
    _, account_other = await create_sold_account(use_redis)

    account_result = await get_sold_accounts_by_account_id(account.sold_account_id)

    assert account.model_dump() == account_result.model_dump()