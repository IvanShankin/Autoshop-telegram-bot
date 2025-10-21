import pytest

from src.services.redis.filling_redis import filling_all_types_account_service, filling_all_account_services
from src.services.database.selling_accounts.actions import get_all_types_account_service, get_type_account_service, \
    get_all_account_services, get_account_service, get_account_categories_by_category_id, \
    get_account_categories_by_parent_id, get_product_account_by_category_id, get_product_account_by_account_id, \
    get_sold_accounts_by_owner_id, get_sold_accounts_by_account_id

@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_all_types_account_service(use_redis, create_type_account_service):
    service_1 = await create_type_account_service()
    service_2 = await create_type_account_service()
    if use_redis: await filling_all_types_account_service()

    list_types = await get_all_types_account_service()
    list_types = [type_service.to_dict() for type_service in list_types]

    assert len(list_types) == 2
    assert service_1.to_dict() in list_types
    assert service_2.to_dict() in list_types


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_all_types_account_service(use_redis, create_type_account_service):
    service_1 = await create_type_account_service(filling_redis=use_redis)
    service_other = await create_type_account_service(filling_redis=use_redis)

    service_type = await get_type_account_service(service_1.type_account_service_id)

    assert service_type.to_dict() == service_1.to_dict()

@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_all_account_services(use_redis, create_type_account_service, create_account_service):
    service_2 = await create_account_service(filling_redis=use_redis, index=2)
    service_1 = await create_account_service(filling_redis=use_redis, index=1)
    if use_redis: await filling_all_account_services()

    list_service = await get_all_account_services()
    list_service = [type_service.to_dict() for type_service in list_service]

    assert len(list_service) == 2
    assert service_1.to_dict() == list_service[0]
    assert service_2.to_dict() == list_service[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_all_types_account_service(use_redis, create_account_service):
    service_1 = await create_account_service(filling_redis=use_redis, show=True)
    service_other = await create_account_service(filling_redis=use_redis, show=True)

    service_type = await get_account_service(service_1.account_service_id, return_not_show=True)

    assert service_type.to_dict() == service_1.to_dict()


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_account_categories_by_category_id(use_redis, create_account_category):
    category_1 = await create_account_category(filling_redis=use_redis)
    category_other = await create_account_category(filling_redis=use_redis)

    result_category = await get_account_categories_by_category_id(category_1.account_category_id, return_not_show=True)

    assert category_1 == result_category

@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_account_categories_by_parent_id(use_redis, create_account_category, create_account_service):
    service = await create_account_service()

    category_owner = await create_account_category(filling_redis=use_redis)
    category_3 = await create_account_category(
        filling_redis=use_redis,
        account_service_id=service.account_service_id,
        parent_id=category_owner.account_category_id,
        index=3
    )
    category_1 = await create_account_category(
        filling_redis=use_redis,
        account_service_id=service.account_service_id,
        parent_id=category_owner.account_category_id,
        index=1
    )
    category_2 = await create_account_category(
        filling_redis=use_redis,
        account_service_id=service.account_service_id,
        parent_id=category_owner.account_category_id,
        index=2
    )

    category_other = await create_account_category(filling_redis=use_redis,)

    list_category = await get_account_categories_by_parent_id(service.account_service_id, category_owner.account_category_id)
    list_category = [category.model_dump() for category in list_category]

    # должны быть отсортированы по индексам
    assert len(list_category) == 3
    assert category_1.model_dump() == list_category[0]
    assert category_2.model_dump() == list_category[1]
    assert category_3.model_dump() == list_category[2]

@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_product_account_by_category_id(use_redis, create_account_category, create_product_account):
    category = await create_account_category()
    account_1 = await create_product_account(use_redis, account_category_id=category.account_category_id)
    account_2 = await create_product_account(use_redis, account_category_id=category.account_category_id)
    account_other = await create_product_account(use_redis)

    list_account = await get_product_account_by_category_id(category.account_category_id)
    list_account = [account.to_dict() for account in list_account]

    assert len(list_account) == 2
    assert account_1.to_dict() in list_account
    assert account_2.to_dict() in list_account

@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_product_account_by_account_id(use_redis, create_account_category, create_product_account):
    category = await create_account_category()
    account = await create_product_account(use_redis, account_category_id=category.account_category_id)
    account_other = await create_product_account(use_redis)

    account_result = await get_product_account_by_account_id(account.account_id)

    assert account.to_dict() == account_result.to_dict()


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_accounts_by_owner_id(use_redis, create_new_user, create_sold_account):
    owner = await create_new_user()
    account_1 = await create_sold_account(use_redis, owner_id=owner.user_id)
    account_2 = await create_sold_account(use_redis, owner_id=owner.user_id)
    account_other = await create_sold_account(use_redis)

    list_account = await get_sold_accounts_by_owner_id(owner.user_id, owner.language)
    list_account = [account.model_dump() for account in list_account]

    # должен быть отсортирован по возрастанию даты
    assert len(list_account) == 2
    assert account_2.model_dump() == list_account[0]
    assert account_1.model_dump() == list_account[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_accounts_by_account_id(use_redis, create_sold_account):
    account = await create_sold_account(use_redis)
    account_other = await create_sold_account(use_redis)

    account_result = await get_sold_accounts_by_account_id(account.sold_account_id)

    assert account.model_dump() == account_result.model_dump()


