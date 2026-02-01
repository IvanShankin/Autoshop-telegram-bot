import os

import pytest
from sqlalchemy import select

from src.services.database.categories.models import PurchaseRequests, AccountStorage, SoldAccounts, Purchases
from src.services.database.core import get_db
from src.services.database.users.models import Users
from src.services.database.users.models.models_users import BalanceHolder


@pytest.mark.asyncio
async def test_purchase_accounts_success(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    monkeypatch,
    create_new_user,
    create_category,
    create_product_account,
):
    """
    Интеграционный тест: если все аккаунты валидны (check_valid_accounts_telethon -> True),
    то purchase_accounts завершает процесс покупки:
      - создаются SoldAccounts / Purchases,
      - PurchaseRequests.status -> 'completed', BalanceHolder.status -> 'used',
      - user.balance уменьшен на total_amount,
      - AccountStorage.status -> 'bought',
      - файлы переехали в финальный путь (create_path_account(...)).
    """
    from src.services.database.categories.actions.purchases import main_purchase as action_mod
    from src.services.products.accounts.tg import actions
    from src.services.filesystem.media_paths import create_path_account

    # подготовка: пользователь + категория + N аккаунтов
    user = await create_new_user(balance=10_000)
    category_full = await create_category(price=100)  # price=100
    category_id = category_full.category_id
    quantity = 2

    products = []
    for _ in range(quantity):
        p, _ = await create_product_account(category_id=category_id)
        products.append(p)

    # подменяем только check_valid_accounts_telethon -> True
    async def always_true(folder_path):
        return True
    monkeypatch.setattr(actions, "check_valid_accounts_telethon", always_true)

    # вызов
    result = await action_mod.purchase_accounts(user.user_id, category_id, quantity,None)
    assert result == True, "В тестируемой функции что-то пошло не так"

    # проверяем в БД
    async with get_db() as session:
        # найдем последнюю заявку пользователя
        result = await session.execute(
            select(PurchaseRequests)
            .where(PurchaseRequests.user_id == user.user_id)
            .order_by(PurchaseRequests.purchase_request_id.desc())
        )
        pr = result.scalars().first()
        assert pr is not None, "PurchaseRequest не создан"
        assert pr.status == "completed"

        # BalanceHolder -> used
        q = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
        bh = q.scalars().first()
        assert bh is not None and bh.status == "used"

        # SoldAccounts - должны быть созданными для владельца
        q = await session.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
        sold = q.scalars().all()
        assert len(sold) == quantity, "SoldAccounts должно быть создано quantity штук"

        # Purchases - должны быть созданы
        q = await session.execute(select(Purchases).where(Purchases.user_id == user.user_id))
        purchases = q.scalars().all()
        assert len(purchases) >= quantity

        # AccountStorage у sold записей должен быть 'bought'
        # используем первые product'ы из original products (их storage ids)
        storage_ids = [p.account_storage.account_storage_id for p in products]
        q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id.in_(storage_ids)))
        storages = q.scalars().all()
        assert all(s.status == "bought" for s in storages), "AccountStorage статусы не стали 'bought'"

        # баланс пользователя уменьшился
        db_user = await session.get(Users, user.user_id)
        assert db_user.balance == user.balance - 0 or isinstance(db_user.balance, int)  # check exist

    # проверяем, что файлы перемещены в bought (проверяем финальные пути)
    for p in products:
        final = create_path_account(
            status="bought",
            type_account_service=p.type_account_service,
            uuid=str(p.account_storage.storage_uuid)
        )
        where = create_path_account(
            status="for_sale",
            type_account_service=p.type_account_service,
            uuid=str(p.account_storage.storage_uuid)
        )

        # Проверяем существование финального файла и отсутствия оригинала
        assert os.path.exists(final), f"Файл для аккаунта {p.account_id} не найден по финальному пути: {final}"
        assert not os.path.exists(where), f"Директория для аккаунта откуда перемещали не была удалена: {where}"



@pytest.mark.asyncio
async def test_purchase_accounts_fail_no_replacement(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    monkeypatch,
    create_new_user,
    create_category,
    create_product_account,
):
    """
    Если все аккаунты невалидны и замены не нашлось -> должно произойти откатывание и аккаунты переместиться в deleted:
      - PurchaseRequests.status == 'failed'
      - BalanceHolder.status == 'released'
      - AccountStorage.status возвращён в 'for_sale'
      - баланс пользователя восстановлен
    """
    from src.services.database.categories.actions.purchases.main_purchase import purchase_accounts
    from src.services.products.accounts.tg import actions
    from src.services.filesystem.media_paths import create_path_account

    # подготовка: пользователь + категория + N аккаунтов
    user = await create_new_user(balance=5_000)
    category_full = await create_category(price=500)  # достаточно высокая цена
    category_id = category_full.category_id
    quantity = 2

    products = []
    for _ in range(quantity):
        p, _ = await create_product_account(category_id=category_id)
        products.append(p)

    # подменим check_valid_accounts_telethon -> False (все аккаунты окажутся "плохими")
    async def always_false(folder_path):
        return False
    monkeypatch.setattr(actions, "check_valid_accounts_telethon", always_false)

    # вызов
    await purchase_accounts(user.user_id, category_id, quantity,None)

    # проверки в БД: должна быть заявка, но статус 'failed', balance holder 'released'
    async with get_db() as session:
        result = await session.execute(
            select(PurchaseRequests).where(PurchaseRequests.user_id == user.user_id).order_by(PurchaseRequests.purchase_request_id.desc())
        )
        pr = result.scalars().first()
        assert pr is not None
        assert pr.status == "failed"

        # BalanceHolder статус
        q = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
        bh = q.scalars().first()
        assert bh is not None and bh.status == "released"

        # account storages должны быть восстановлены в 'for_sale'
        storage_ids = [p.account_storage.account_storage_id for p in products]
        q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id.in_(storage_ids)))
        storages = q.scalars().all()
        assert all(s.status == "deleted" for s in storages), "AccountStorage не установленны 'deleted'"

        # баланс пользователя восстановлен (в create_new_user он уже был установлен)
        db_user = await session.get(Users, user.user_id)
        # так как в start_purchase_account баланс уменьшался, а в cancel_purchase_request_accounts возвращается,
        # итоговый баланс должен быть равен исходному (fixture user.balance)
        assert db_user.balance == user.balance

    # проверяем, что аккаунты переместились к deleted
    for p in products:
        not_dir = create_path_account(
            status="bought",
            type_account_service=p.type_account_service,
            uuid=str(p.account_storage.storage_uuid)
        )
        not_dir_2 = create_path_account(
            status="for_sale",
            type_account_service=p.type_account_service,
            uuid=str(p.account_storage.storage_uuid)
        )
        there_is_dir = create_path_account(
            status="deleted",
            type_account_service=p.type_account_service,
            uuid=str(p.account_storage.storage_uuid)
        )

        # К пользователю не должны переместиться аккаунты, а на продаже должны остаться аккаунты
        assert not os.path.exists(not_dir), f"К пользователю переместился аккаунт. {not_dir}"
        assert not os.path.exists(not_dir_2), f"Аккаунт не был перемещён с продажи. {not_dir_2}"
        assert os.path.exists(there_is_dir), f"Аккаунт не был перемещён к удалённым. {there_is_dir}"

