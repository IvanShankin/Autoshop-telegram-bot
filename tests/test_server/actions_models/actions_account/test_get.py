import pytest

from src.services.redis.filling_redis import filling_account_categories_by_category_id



@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_account_categories_by_category_id(use_redis, create_category, create_product_account):
    from src.services.database.product_categories.actions import get_account_categories_by_category_id

    category_1 = await create_category(filling_redis=use_redis)
    category_other = await create_category(filling_redis=use_redis)
    _ = await create_product_account(filling_redis=use_redis, category_id=category_1.category_id)
    category_1.quantity_product = 1
    if use_redis:
        await filling_account_categories_by_category_id() # для поддержания актуальных данных в redis

    result_category = await get_account_categories_by_category_id(category_1.category_id, return_not_show=True)

    assert category_1 == result_category


@pytest.mark.asyncio
async def test_get_all_phone_in_account_storage(create_account_service, create_product_account, create_sold_account):
    from src.services.database.product_categories.actions import get_all_phone_in_account_storage

    service = await create_account_service()
    _, account_1 = await create_product_account(type_account_service_id=service.type_account_service_id)
    account_2, _ = await create_sold_account(type_account_service_id=service.type_account_service_id, phone_number = "+7 32949 543543")

    all_phones = await get_all_phone_in_account_storage(service.type_account_service_id)

    assert account_1.account_storage.phone_number in all_phones
    assert account_2.phone_number in all_phones



@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_account_categories_by_parent_id(use_redis, create_category, create_account_service, create_product_account):
    from src.services.database.product_categories.actions import get_account_categories_by_parent_id

    service = await create_account_service()

    category_owner = await create_category(filling_redis=use_redis)
    category_3 = await create_category(
        filling_redis=use_redis,
        account_service_id=service.account_service_id,
        is_product_storage=True,
        parent_id=category_owner.category_id,
        index=3
    )
    category_1 = await create_category(
        filling_redis=use_redis,
        account_service_id=service.account_service_id,
        is_product_storage=True,
        parent_id=category_owner.category_id,
        index=1
    )
    category_2 = await create_category(
        filling_redis=use_redis,
        account_service_id=service.account_service_id,
        is_product_storage=True,
        parent_id=category_owner.category_id,
        index=2
    )
    _ = await create_product_account(filling_redis=use_redis, category_id=category_3.category_id)
    _ = await create_product_account(filling_redis=use_redis, category_id=category_2.category_id)
    _ = await create_product_account(filling_redis=use_redis, category_id=category_1.category_id)
    category_3.quantity_product = 1
    category_2.quantity_product = 1
    category_1.quantity_product = 1

    category_other = await create_category(filling_redis=use_redis,)

    list_category = await get_account_categories_by_parent_id(service.account_service_id, category_owner.category_id)
    list_category = [category.model_dump() for category in list_category]

    # должны быть отсортированы по индексам
    assert len(list_category) == 3
    assert category_1.model_dump() == list_category[0]
    assert category_2.model_dump() == list_category[1]
    assert category_3.model_dump() == list_category[2]


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_product_account_by_category_id(use_redis, create_category, create_product_account):
    from src.services.database.product_categories.actions import get_product_account_by_category_id

    category = await create_category()
    account_1, _ = await create_product_account(use_redis, category_id=category.category_id)
    account_2, _ = await create_product_account(use_redis, category_id=category.category_id)
    account_other, _ = await create_product_account(use_redis)

    list_account = await get_product_account_by_category_id(category.category_id)
    list_account = [account.to_dict() for account in list_account]

    assert len(list_account) == 2
    assert account_1.to_dict() in list_account
    assert account_2.to_dict() in list_account


@pytest.mark.asyncio
async def test_get_full_product_account_by_category_id(create_category, create_product_account):
    from src.services.database.product_categories.actions import get_product_account_by_category_id

    category = await create_category()
    _, account_1 = await create_product_account(category_id=category.category_id)
    _, account_2 = await create_product_account(category_id=category.category_id)
    _, account_other = await create_product_account()

    list_account = await get_product_account_by_category_id(category.category_id, get_full=True)
    list_account = [account.model_dump() for account in list_account]

    assert len(list_account) == 2
    assert account_1.model_dump() in list_account
    assert account_2.model_dump() in list_account


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_product_account_by_account_id(use_redis, create_category, create_product_account):
    from src.services.database.product_categories.actions import get_product_account_by_account_id
    category = await create_category()
    _, account = await create_product_account(use_redis, category_id=category.category_id)
    _, account_other = await create_product_account(use_redis)

    account_result = await get_product_account_by_account_id(account.account_id)
    assert account == account_result


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_accounts_by_owner_id(use_redis, create_new_user, create_sold_account):
    from src.services.database.product_categories.actions import get_sold_accounts_by_owner_id

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
    from src.services.database.product_categories.actions import get_sold_account_by_page

    owner = await create_new_user()
    account_1, _ = await create_sold_account(use_redis, owner_id=owner.user_id)
    account_2, _ = await create_sold_account(use_redis, type_account_service_id=account_1.type_account_service_id, owner_id=owner.user_id)
    account_other, _ = await create_sold_account(use_redis)

    list_account = await get_sold_account_by_page(owner.user_id, account_1.type_account_service_id, 1, owner.language)
    list_account = [account.model_dump() for account in list_account]

    # должен быть отсортирован по возрастанию даты
    assert len(list_account) == 2
    assert account_2.model_dump() == list_account[0]
    assert account_1.model_dump() == list_account[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_accounts_by_account_id(use_redis, create_sold_account):
    from src.services.database.product_categories.actions import get_sold_accounts_by_account_id

    _, account = await create_sold_account(use_redis)
    _, account_other = await create_sold_account(use_redis)

    account_result = await get_sold_accounts_by_account_id(account.sold_account_id)

    assert account.model_dump() == account_result.model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_union_type_account_service_id(use_redis, create_sold_account):
    from src.services.database.product_categories.actions import get_union_type_account_service_id

    _, account_1 = await create_sold_account(use_redis)
    _, account_2 = await create_sold_account(
        use_redis, type_account_service_id=account_1.type_account_service_id, owner_id=account_1.owner_id
    )
    _, account_3 = await create_sold_account(use_redis, owner_id=account_1.owner_id)

    result = await get_union_type_account_service_id(account_1.owner_id)

    assert 2 == len(result)
    assert account_1.type_account_service_id in result
    assert account_3.type_account_service_id in result


@pytest.mark.asyncio
async def test_subtree_with_visible_storage_returns_true(create_category, create_product_account):
    """
    root -> child -> grand
    grand.is_product_storage=True и в grand есть аккаунт
    все show=True -> root/child/grand => True
    """
    from src.services.database.product_categories.actions.actions_get import _has_accounts_in_subtree
    # создаём дерево
    root = await create_category()
    child = await create_category(parent_id=root.category_id)
    grand = await create_category(
        parent_id=child.category_id,
        is_product_storage=True
    )

    # создаём аккаунт в категории grand
    await create_product_account(category_id=grand.category_id)

    # обновляем quantity в DTO (fixture возвращает DTO на момент создания)
    grand.quantity_product = 1

    all_cats = [root, child, grand]

    assert _has_accounts_in_subtree(grand, all_cats) is True
    assert _has_accounts_in_subtree(child, all_cats) is True
    assert _has_accounts_in_subtree(root, all_cats) is True


@pytest.mark.asyncio
async def test_subtree_blocked_by_hidden_node(create_category, create_product_account):
    """
    root -> child (show=False) -> grand(is_product_storage=True, has account)
    child.show == False => child и root должны вернуть False, grand True
    """
    from src.services.database.product_categories.actions.actions_get import _has_accounts_in_subtree
    root = await create_category()
    # child скрыт
    child = await create_category(parent_id=root.category_id, show=False)
    grand = await create_category(
        parent_id=child.category_id,
        is_product_storage=True
    )

    await create_product_account(category_id=grand.category_id)
    grand.quantity_product = 1

    all_cats = [root, child, grand]

    assert _has_accounts_in_subtree(grand, all_cats) is True
    # child скрыт — его ветвь не учитывается
    assert _has_accounts_in_subtree(child, all_cats) is False
    # root не должен "видеть" аккаунты через скрытую ветвь
    assert _has_accounts_in_subtree(root, all_cats) is False


@pytest.mark.asyncio
async def test_subtree_wide_siblings_only_one_branch_has_accounts(create_category, create_product_account):
    """
    root -> many children (child_0..child_4)
    child_2 -> grand_target(is_product_storage=True, has account)
    Ожидаем: root True; child_2 True; другие child False
    """
    from src.services.database.product_categories.actions.actions_get import _has_accounts_in_subtree
    root = await create_category()
    children = []
    for _i in range(5):
        c = await create_category(parent_id=root.category_id)
        children.append(c)

    # делаем поддерево у child[2]
    grand_target = await create_category(
        parent_id=children[2].category_id,
        is_product_storage=True
    )

    await create_product_account(category_id=grand_target.category_id)
    grand_target.quantity_product = 1

    all_cats = [root] + children + [grand_target]

    # root должен видеть аккаунт
    assert _has_accounts_in_subtree(root, all_cats) is True

    # только ветка с индексом 2 активна
    for idx, child in enumerate(children):
        if idx == 2:
            assert _has_accounts_in_subtree(child, all_cats) is True
        else:
            assert _has_accounts_in_subtree(child, all_cats) is False


@pytest.mark.asyncio
async def test_update_tg_account_media(create_tg_account_media):
    from src.services.database.product_categories.actions import get_tg_account_media

    tg_media = await create_tg_account_media()
    result_tg_media = await get_tg_account_media(tg_media.account_storage_id)

    assert tg_media.to_dict() == result_tg_media.to_dict()