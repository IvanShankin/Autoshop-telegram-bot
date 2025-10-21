import asyncio

import pytest
from orjson import orjson
from sqlalchemy import select

from src.exceptions.service_exceptions import NotEnoughAccounts, NotEnoughMoney, InvalidPromoCode
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db
from src.services.database.discounts.models import PromoCodes

from src.services.database.selling_accounts.models import SoldAccounts, PurchasesAccounts, \
    SoldAccountsTranslation
from src.services.database.selling_accounts.models.schemas import PurchaseAccountSchem
from src.services.database.users.models import UserAuditLogs, Users


async def _get_user_from_db(user_id: int) -> Users:
    async with get_db() as s:
        r = await s.execute(select(Users).where(Users.user_id == user_id))
        return r.scalar_one()


async def _count_user_audit_logs_for_user(user_id: int) -> int:
    async with get_db() as s:
        r = await s.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == user_id))
        return len(r.scalars().all())


@pytest.mark.asyncio
async def test_purchase_accounts_with_amount_promo(
    replacement_needed_modules,
    start_consumer,
    clean_rabbit,
    create_new_user,
    create_type_account_service,
    create_account_service,
    create_account_category,
    create_translate_account_category,
    create_product_account,
    create_promo_code,
):
    from src.services.database.selling_accounts.actions.action_purchase import purchase_accounts
    # подготовка данных
    user = await create_new_user()
    # выставим баланс пользователя (через DB), чтобы хватило денег
    async with get_db() as s:
        await s.execute(select(Users))
        await s.execute(Users.__table__.update().where(Users.user_id == user.user_id).values(balance=10_000))
        await s.commit()

    # создаём сервис/категорию/перевод/несколько product accounts
    type_service = await create_type_account_service(filling_redis=True)
    service = await create_account_service(filling_redis=True, type_account_service_id=type_service.type_account_service_id)
    category_full = await create_account_category(filling_redis=True, account_service_id=service.account_service_id)
    # добавляем перевод для category (чтобы purchase_accounts мог взять translations_category)
    await create_translate_account_category(category_full.account_category_id,filling_redis=True, language='en')


    # добавляем три product accounts
    pa1 = await create_product_account(filling_redis=True,
                                       type_account_service_id=type_service.type_account_service_id,
                                       account_category_id=category_full.account_category_id)
    pa2 = await create_product_account(filling_redis=True,
                                       type_account_service_id=type_service.type_account_service_id,
                                       account_category_id=category_full.account_category_id)
    pa3 = await create_product_account(filling_redis=True,
                                       type_account_service_id=type_service.type_account_service_id,
                                       account_category_id=category_full.account_category_id)

    # промокод (fixture create_promo_code создаёт промокод amount=100 по умолчанию)
    promo = create_promo_code

    # вызов тестируемой функции
    result: PurchaseAccountSchem = await purchase_accounts(
        user_id=user.user_id,
        category_id=category_full.account_category_id,
        quantity_accounts=3,
        code_promo_code=promo.activation_code
    )

    # проверки DB: sold accounts и purchases
    async with get_db() as s:
        sold_rows = (await s.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))).scalars().all()
        purchases = (await s.execute(select(PurchasesAccounts).where(PurchasesAccounts.user_id == user.user_id))).scalars().all()
        translations = (await s.execute(select(SoldAccountsTranslation))).scalars().all()

    assert len(sold_rows) >= 3, "должны появиться проданные аккаунты"
    assert len(purchases) >= 3, "должны появиться записи о покупках"
    assert len(translations) >= 6, "должны появиться записи перевода у купленных аккаунтов"

    # сумма по purchase_price должна равняться рассчитанному final_total
    original_total = category_full.price_one_account * 3
    expected_discount = min(promo.amount, original_total) if promo.amount else (original_total * promo.discount_percentage) // 100
    expected_final = original_total - expected_discount

    sum_purchase_prices = sum(p.purchase_price for p in purchases)
    assert sum_purchase_prices == expected_final

    # возврат функции — ids должны соответствовать созданным sold_accounts
    assert isinstance(result, PurchaseAccountSchem)
    assert len(result.ids_new_sold_account) == 3
    assert all(isinstance(i, int) for i in result.ids_new_sold_account)

    # проверяем Redis обновлён (product_accounts_by_category_id должен теперь либо быть короче, либо пуст)
    async with get_redis() as r:
        key = f"product_accounts_by_category_id:{category_full.account_category_id}"
        raw = await r.get(key)
        if raw:
            arr = orjson.loads(raw)
            # убеждаемся, что удалённые аккаунты не присутствуют
            deleted_ids = set(result.ids_deleted_product_account)
            remaining_ids = {item.get("account_id") for item in arr}
            assert deleted_ids.isdisjoint(remaining_ids)

    # ждём, чтобы consumer обработал событие покупки и записал UserAuditLogs (handler_new_purchase)
    # проверяем в цикле до timeout
    timeout = 4.0
    waited = 0.0
    found_logs = 0
    interval = 0.2
    while waited < timeout:
        async with get_db() as s:
            r = await s.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id))
            logs = r.scalars().all()
            if logs:
                found_logs = len(logs)
                break
        await asyncio.sleep(interval)
        waited += interval

    assert found_logs >= 1, "ожидалось, что consumer обработает событие покупки и создаст хотя бы один UserAuditLogs"

@pytest.mark.asyncio
async def test_purchase_accounts_without_promo(
    replacement_needed_modules,
    start_consumer,
    clean_rabbit,
    create_new_user,
    create_type_account_service,
    create_account_service,
    create_account_category,
    create_translate_account_category,
    create_product_account,
):
    from src.services.database.selling_accounts.actions.action_purchase import purchase_accounts
    # подготовим пользователя и данные
    user = await create_new_user()
    async with get_db() as s:
        await s.execute(Users.__table__.update().where(Users.user_id == user.user_id).values(balance=10_000))
        await s.commit()

    type_service = await create_type_account_service(filling_redis=True)
    service = await create_account_service(filling_redis=True, type_account_service_id=type_service.type_account_service_id)
    category_full = await create_account_category(filling_redis=True, account_service_id=service.account_service_id)
    await create_translate_account_category(category_full.account_category_id, filling_redis=True, language='en')

    # добавляем 2 product accounts
    pa1 = await create_product_account(filling_redis=True,
                                       type_account_service_id=type_service.type_account_service_id,
                                       account_category_id=category_full.account_category_id)
    pa2 = await create_product_account(filling_redis=True,
                                       type_account_service_id=type_service.type_account_service_id,
                                       account_category_id=category_full.account_category_id)

    # вызов без promo
    result: PurchaseAccountSchem = await purchase_accounts(
        user_id=user.user_id,
        category_id=category_full.account_category_id,
        quantity_accounts=2,
        code_promo_code=None
    )

    # проверки
    async with get_db() as s:
        sold_rows = (await s.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))).scalars().all()
        purchases = (await s.execute(select(PurchasesAccounts).where(PurchasesAccounts.user_id == user.user_id))).scalars().all()

    assert len(sold_rows) >= 2
    assert len(purchases) >= 2

    # итоговая сумма = original_total (т.к. скидки нет)
    original_total = category_full.price_one_account * 2
    sum_purchase_prices = sum(p.purchase_price for p in purchases)
    assert sum_purchase_prices == original_total

    # Redis: список товаров по категории не содержит удалённых аккаунтов
    async with get_redis() as r:
        key = f"product_accounts_by_category_id:{category_full.account_category_id}"
        raw = await r.get(key)
        if raw:
            arr = orjson.loads(raw)
            remaining_ids = {item.get("account_id") for item in arr}
            deleted_ids = set(result.ids_deleted_product_account)
            assert deleted_ids.isdisjoint(remaining_ids)

    # ждём появления аудита (consumer должен обработать событие)
    timeout = 4.0
    waited = 0.0
    interval = 0.2
    found_logs = 0
    while waited < timeout:
        async with get_db() as s:
            r = await s.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id))
            logs = r.scalars().all()
            if logs:
                found_logs = len(logs)
                break
        await asyncio.sleep(interval)
        waited += interval

    assert found_logs >= 1

@pytest.mark.asyncio
async def test_purchase_accounts_percent_discount(
    create_new_user,
    create_type_account_service,
    create_account_service,
    create_account_category,
    create_translate_account_category,
    create_product_account,
):
    """Промокод процентный"""
    from src.services.database.selling_accounts.actions.action_purchase import purchase_accounts
    user = await create_new_user()
    async with get_db() as s:
        await s.execute(Users.__table__.update().where(Users.user_id == user.user_id).values(balance=10000))
        await s.commit()

    type_service = await create_type_account_service()
    service = await create_account_service(type_account_service_id=type_service.type_account_service_id)
    category = await create_account_category(account_service_id=service.account_service_id, price_one_account=100)

    await create_product_account(type_account_service_id=type_service.type_account_service_id,
                                 account_category_id=category.account_category_id)

    # промокод 50%
    promo = PromoCodes(
        activation_code="HALF",
        min_order_amount=1,
        amount=None,
        discount_percentage=50,
        is_valid=True,
    )
    async with get_db() as s:
        s.add(promo)
        await s.commit()
        await s.refresh(promo)

    result = await purchase_accounts(user.user_id, category.account_category_id, quantity_accounts=1, code_promo_code=promo.activation_code)

    async with get_db() as s:
        purchase = (await s.execute(select(PurchasesAccounts).where(PurchasesAccounts.user_id == user.user_id))).scalars().first()
    assert purchase.purchase_price == 50


@pytest.mark.asyncio
async def test_purchase_accounts_not_enough_accounts(
    create_new_user,
    create_type_account_service,
    create_account_service,
    create_account_category,
    create_translate_account_category,
):
    from src.services.database.selling_accounts.actions.action_purchase import purchase_accounts
    user = await create_new_user()
    async with get_db() as s:
        await s.execute(Users.__table__.update().where(Users.user_id == user.user_id).values(balance=10000))
        await s.commit()

    type_service = await create_type_account_service()
    service = await create_account_service(type_account_service_id=type_service.type_account_service_id)
    category = await create_account_category(account_service_id=service.account_service_id)

    # нет product_accounts
    with pytest.raises(NotEnoughAccounts):
        await purchase_accounts(user.user_id, category.account_category_id, quantity_accounts=2, code_promo_code=None)


@pytest.mark.asyncio
async def test_purchase_accounts_not_enough_money(
    create_new_user,
    create_type_account_service,
    create_account_service,
    create_account_category,
    create_translate_account_category,
    create_product_account,
):
    from src.services.database.selling_accounts.actions.action_purchase import purchase_accounts
    user = await create_new_user()
    # выставляем маленький баланс
    async with get_db() as s:
        await s.execute(Users.__table__.update().where(Users.user_id == user.user_id).values(balance=10))
        await s.commit()

    type_service = await create_type_account_service()
    service = await create_account_service(type_account_service_id=type_service.type_account_service_id)
    category = await create_account_category(account_service_id=service.account_service_id, price_one_account=500)

    await create_product_account(type_account_service_id=type_service.type_account_service_id,
                                 account_category_id=category.account_category_id)

    with pytest.raises(NotEnoughMoney):
        await purchase_accounts(user.user_id, category.account_category_id, quantity_accounts=1, code_promo_code=None)

@pytest.mark.asyncio
async def test_purchase_accounts_invalid_promo(
    create_new_user,
    create_type_account_service,
    create_account_service,
    create_account_category,
    create_translate_account_category,
    create_product_account,
):
    from src.services.database.selling_accounts.actions.action_purchase import purchase_accounts
    user = await create_new_user()
    async with get_db() as s:
        await s.execute(Users.__table__.update().where(Users.user_id == user.user_id).values(balance=10000))
        await s.commit()

    type_service = await create_type_account_service()
    service = await create_account_service(type_account_service_id=type_service.type_account_service_id)
    category = await create_account_category(account_service_id=service.account_service_id)

    await create_product_account(type_account_service_id=type_service.type_account_service_id,
                                 account_category_id=category.account_category_id)

    with pytest.raises(InvalidPromoCode):
        await purchase_accounts(user.user_id, category.account_category_id, quantity_accounts=1, code_promo_code="FAKECODE")
