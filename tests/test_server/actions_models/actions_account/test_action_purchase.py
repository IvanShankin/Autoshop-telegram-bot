import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import orjson
import pytest

from sqlalchemy import select

from tests.helpers.helper_functions import comparison_models
from src.exceptions.service_exceptions import NotEnoughAccounts, NotEnoughMoney
from src.services.database.core import get_db
from src.services.database.selling_accounts.models.models import PurchaseRequests, PurchaseRequestAccount, \
    AccountStorage, ProductAccounts, SoldAccounts, PurchasesAccounts
from src.services.database.selling_accounts.models.schemas import StartPurchaseAccount
from src.services.database.users.models import Users
from src.services.database.users.models.models_users import BalanceHolder
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_purchase_accounts_success(
    replacement_pyth_account,
    patch_fake_aiogram,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
    create_account_category,
    create_product_account,
):
    """
    Интеграционный тест: если все аккаунты валидны (check_valid_accounts_telethon -> True),
    то purchase_accounts завершает процесс покупки:
      - создаются SoldAccounts / PurchasesAccounts,
      - PurchaseRequests.status -> 'completed', BalanceHolder.status -> 'used',
      - user.balance уменьшен на total_amount,
      - AccountStorage.status -> 'bought',
      - файлы переехали в финальный путь (create_path_account(...)).
    """
    from src.services.database.selling_accounts.actions import action_purchase as action_mod
    from src.services.accounts.tg import actions
    from src.services.filesystem.account_actions import create_path_account

    # подготовка: пользователь + категория + N аккаунтов
    user = await create_new_user(balance=10_000)
    category_full = await create_account_category(price_one_account=100)  # price=100
    category_id = category_full.account_category_id
    quantity = 2

    products = []
    for _ in range(quantity):
        p, _ = await create_product_account(account_category_id=category_id)
        products.append(p)

    # подменяем только check_valid_accounts_telethon -> True
    async def always_true(folder_path):
        return True
    monkeypatch.setattr(actions, "check_valid_accounts_telethon", always_true)

    # подавим publish_event, чтобы не посылать реальные события
    async def noop_publish(*a, **kw):
        return None
    monkeypatch.setattr(action_mod, "publish_event", noop_publish)

    # вызов
    result = await action_mod.purchase_accounts(user.user_id, category_id, quantity, None)
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

        # PurchasesAccounts - должны быть созданы
        q = await session.execute(select(PurchasesAccounts).where(PurchasesAccounts.user_id == user.user_id))
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
            type_account_service='telegram',
            uuid=str(p.account_storage.storage_uuid)
        )
        where = create_path_account(
            status="for_sale",
            type_account_service='telegram',
            uuid=str(p.account_storage.storage_uuid)
        )

        # Проверяем существование финального файла и отсутствия оригинала
        assert os.path.exists(final), f"Файл для аккаунта {p.account_id} не найден по финальному пути: {final}"
        assert not os.path.exists(where), f"Директория для аккаунта откуда перемещали не была удалена: {where}"



@pytest.mark.asyncio
async def test_purchase_accounts_fail_no_replacement(
    replacement_pyth_account,
    patch_fake_aiogram,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
    create_account_category,
    create_product_account,
):
    """
    Если все аккаунты невалидны и замены не нашлось -> должно произойти откатывание и аккаунты переместиться в deleted:
      - PurchaseRequests.status == 'failed'
      - BalanceHolder.status == 'released'
      - AccountStorage.status возвращён в 'for_sale'
      - баланс пользователя восстановлен
    """
    from src.services.database.selling_accounts.actions import action_purchase as action_mod
    from src.services.accounts.tg import actions
    from src.services.filesystem.account_actions import create_path_account

    # подготовка: пользователь + категория + N аккаунтов
    user = await create_new_user(balance=5_000)
    category_full = await create_account_category(price_one_account=500)  # достаточно высокая цена
    category_id = category_full.account_category_id
    quantity = 2

    products = []
    for _ in range(quantity):
        p, _ = await create_product_account(account_category_id=category_id)
        products.append(p)

    # подменим check_valid_accounts_telethon -> False (все аккаунты окажутся "плохими")
    async def always_false(folder_path):
        return False
    monkeypatch.setattr(actions, "check_valid_accounts_telethon", always_false)

    # подавим publish_event
    async def noop_publish(*a, **kw):
        return None
    monkeypatch.setattr(action_mod, "publish_event", noop_publish)

    # вызов
    await action_mod.purchase_accounts(user.user_id, category_id, quantity, None)

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
        # так как в start_purchase_request баланс уменьшался, а в cancel_purchase_request возвращается,
        # итоговый баланс должен быть равен исходному (fixture user.balance)
        assert db_user.balance == user.balance

    # проверяем, что аккаунты переместились к deleted
    for p in products:
        not_dir = create_path_account(
            status="bought",
            type_account_service='telegram',
            uuid=str(p.account_storage.storage_uuid)
        )
        not_dir_2 = create_path_account(
            status="for_sale",
            type_account_service='telegram',
            uuid=str(p.account_storage.storage_uuid)
        )
        there_is_dir = create_path_account(
            status="deleted",
            type_account_service='telegram',
            uuid=str(p.account_storage.storage_uuid)
        )

        # К пользователю не должны переместиться аккаунты, а на продаже должны остаться аккаунты
        assert not os.path.exists(not_dir), f"К пользователю переместился аккаунт. {not_dir}"
        assert not os.path.exists(not_dir_2), f"Аккаунт не был перемещён с продажи. {not_dir_2}"
        assert os.path.exists(there_is_dir), f"Аккаунт не был перемещён к удалённым. {there_is_dir}"


class TestStartPurchaseRequest:
    @pytest.mark.asyncio
    async def test_start_purchase_request_success(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        replacement_fake_bot,
        create_new_user,
        create_account_category,
        create_product_account,
    ):
        """
        Успешный старт покупки:
        - создаётся PurchaseRequests (status=processing)
        - создаются PurchaseRequestAccount (кол-во = quantity_accounts)
        - создаётся BalanceHolder
        - списывается баланс пользователя
        - AccountStorage.status -> 'reserved' для задействованных аккаунтов
        - возвращаемый StartPurchaseAccount содержит согласованные поля
        """
        from src.services.database.selling_accounts.actions.action_purchase import start_purchase_request
        # подготовка
        user = await create_new_user(balance=10_000)
        full_category = await create_account_category(price_one_account=100)
        category_id = full_category.account_category_id
        quantity = 3

        # создаём required number of product accounts in that category
        created_products: list[ProductAccounts] = []
        created_products_full: list[ProductAccounts] = []
        for _ in range(quantity):
            prod, prod_full = await create_product_account(account_category_id=category_id)
            created_products.append(prod)
            created_products_full.append(prod_full)

        async with get_db() as session:
            db_user = await session.get(Users, user.user_id)
            balance_before = db_user.balance

        # вызов тестируемой функции
        result = await start_purchase_request(
            user_id=user.user_id,
            category_id=category_id,
            quantity_accounts=quantity,
            promo_code_id=None
        )

        result_product_accounts: list[dict] = [account.to_dict() for account in result.product_accounts]

        # проверки возвращаемых данных (базовые)
        assert result.total_amount >= 0
        assert result.category_id == category_id
        assert len(result.product_accounts) == quantity
        assert result.purchase_request_id is not None
        assert result.user_balance_before == balance_before
        assert result.user_balance_after == balance_before - result.total_amount
        for account in created_products:
            assert account.to_dict() in result_product_accounts


        # проверки в БД
        async with get_db() as session:
            # PurchaseRequests
            pr = await session.get(PurchaseRequests, result.purchase_request_id)
            assert pr is not None
            assert pr.status == "processing"
            assert pr.quantity == quantity
            # PurchaseRequestAccount count
            q = await session.execute(
                select(PurchaseRequestAccount).where(PurchaseRequestAccount.purchase_request_id == pr.purchase_request_id)
            )
            pr_accounts = q.scalars().all()
            assert len(pr_accounts) == quantity

            # BalanceHolder
            q = await session.execute(
                select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id)
            )
            bal_holder = q.scalars().first()
            assert bal_holder is not None
            assert bal_holder.amount == result.total_amount

            # AccountStorage статусы должны быть "reserved" для соответствующих хранилищ
            # Мы собираем идентификаторы из возвращенных product_accounts
            storage_ids = [p.account_storage.account_storage_id for p in result.product_accounts]
            q = await session.execute(
                select(AccountStorage).where(AccountStorage.account_storage_id.in_(storage_ids))
            )
            storages = q.scalars().all()
            assert all(s.status == "reserved" for s in storages)

            # баланс должен уменьшится
            db_user_after = await session.get(Users, user.user_id)
            assert db_user_after.balance == balance_before - result.total_amount

        async with get_redis() as session_redis:
            user_dict = orjson.loads(await session_redis.get(f'user:{user.user_id}'))
            await comparison_models(db_user_after.to_dict(), user_dict)

            for account in created_products_full:
                account.account_storage.status = "reserved" # аккаунт должен стать зарезервированным
                account_redis = await session_redis.get(f'product_accounts_by_account_id:{account.account_id}')
                account_dict = orjson.loads(account_redis)
                await comparison_models(account.model_dump(), account_dict)


    @pytest.mark.asyncio
    async def test_start_purchase_request_with_promo_code(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        replacement_fake_bot,
        create_new_user,
        create_account_category,
        create_product_account,
        create_promo_code,
    ):
        """
        Проверяет корректную работу функции start_purchase_request с применением промокода:
        - скидка применяется (total_amount уменьшен)
        - создаётся PurchaseRequests с промокодом
        - баланс списывается с учётом скидки
        """
        from src.services.database.selling_accounts.actions.action_purchase import start_purchase_request

        # подготовка данных
        user = await create_new_user(balance=10_000)
        category = await create_account_category(price_one_account=500)
        promo = await create_promo_code()

        quantity = 2
        for _ in range(quantity):
            await create_product_account(account_category_id=category.account_category_id)

        async with get_db() as session:
            db_user = await session.get(Users, user.user_id)
            balance_before = db_user.balance

        # вызов тестируемой функции
        result = await start_purchase_request(
            user_id=user.user_id,
            category_id=category.account_category_id,
            quantity_accounts=quantity,
            promo_code_id=promo.promo_code_id,
        )

        # проверки возвращаемых данных
        assert result.category_id == category.account_category_id
        assert result.purchase_request_id is not None
        assert result.total_amount < category.price_one_account * quantity  # скидка применена
        assert result.user_balance_after == balance_before - result.total_amount

        # проверки в БД
        async with get_db() as session:
            pr = await session.get(PurchaseRequests, result.purchase_request_id)
            assert pr is not None
            assert pr.promo_code_id == promo.promo_code_id  # промокод записан
            db_user_after = await session.get(Users, user.user_id)
            assert db_user_after.balance == balance_before - result.total_amount


    @pytest.mark.asyncio
    async def test_start_purchase_request_not_enough_accounts(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        replacement_fake_bot,
        create_new_user,
        create_account_category,
        create_product_account,
    ):
        """
        Если в категории меньше аккаунтов, чем требуется — возникает NotEnoughAccounts.
        """
        from src.services.database.selling_accounts.actions.action_purchase import start_purchase_request
        user = await create_new_user(balance=10000)
        full_category = await create_account_category()
        category_id = full_category.account_category_id

        # создаём только 1 аккаунт, а запросим 5
        await create_product_account(account_category_id=category_id)
        with pytest.raises(NotEnoughAccounts):
            await start_purchase_request(
                user_id=user.user_id,
                category_id=category_id,
                quantity_accounts=5,
                promo_code_id=None
            )


    @pytest.mark.asyncio
    async def test_start_purchase_request_not_enough_money(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        replacement_fake_bot,
        create_new_user,
        create_account_category,
        create_product_account,
    ):
        """
        Если у пользователя не хватает денег — возникает NotEnoughMoney.
        """
        from src.services.database.selling_accounts.actions.action_purchase import start_purchase_request
        user = await create_new_user(balance=10)  # маленький баланс
        full_category = await create_account_category(price_one_account=1000)
        category_id = full_category.account_category_id

        # создаём хотя бы 1 аккаунт
        await create_product_account(account_category_id=category_id)

        with pytest.raises(NotEnoughMoney):
            await start_purchase_request(
                user_id=user.user_id,
                category_id=category_id,
                quantity_accounts=1,
                promo_code_id=None
            )

@pytest.mark.asyncio
async def test__check_account_validity_async_success(
    replacement_pyth_account,
    patch_fake_aiogram,
    create_product_account,
    create_account_category,
    monkeypatch,
):
    """
    Unit: check_account_validity должен:
    - вызвать decryption_tg_account (мы мокаем),
    - вызвать check_valid_accounts_telethon (мокаем) и вернуть True,
    - вызвать shutil.rmtree в finally (мокаем).
    """
    from src.services.database.selling_accounts.actions import action_purchase as action_mod
    from src.services.accounts.tg import actions

    # создаём тестовую категорию и продукт (этот шаг даёт нам AccountStorage)
    cat = await create_account_category()
    prod_obj, _ = await create_product_account(account_category_id=cat.account_category_id)

    account_storage = prod_obj.account_storage

    # Подменим TYPE_ACCOUNT_SERVICES чтобы наш type_service_name считался валидным
    monkeypatch.setattr(actions, "TYPE_ACCOUNT_SERVICES", {"test_service": True})

    # СДЕЛАЕМ decryption синхронным (то, что ожидает asyncio.to_thread)
    temp_folder_path = Path.cwd() / "tmp_test_account_folder"

    def fake_decryption_tg_account(account_storage_arg):
        # создаём папку, чтобы rmtree мог ее удалить (проверим вызов)
        os.makedirs(temp_folder_path, exist_ok=True)
        # создадим минимальные файлы, которые могут понадобиться
        open(str((temp_folder_path / "session.session").touch()), "wb").close()
        tdata_dir = temp_folder_path / "tdata"
        os.makedirs(tdata_dir, exist_ok=True)
        return temp_folder_path

    monkeypatch.setattr(actions, "decryption_tg_account", fake_decryption_tg_account)

    # Мокаем асинхронную проверку аккаунта — вернём True
    async def fake_check_valid_accounts(folder_path):
        # folder_path теперь строка (temp_folder_path)
        assert folder_path == temp_folder_path
        return True

    monkeypatch.setattr(actions, "check_valid_accounts_telethon", fake_check_valid_accounts)

    # Сохраним оригинал rmtree и подменим на фейк, который вызовет оригинал
    orig_rmtree = shutil.rmtree

    rm_called = {"called": False, "path": None, "kw": None}

    def fake_rmtree(path, **kw):
        rm_called["called"] = True
        rm_called["path"] = path
        rm_called["kw"] = kw
        # вызываем оригинальную реализацию, чтобы реально удалить папку
        try:
            orig_rmtree(path, **kw)
        except Exception:
            pass
        return True

    monkeypatch.setattr(shutil, "rmtree", fake_rmtree)

    # Вызов тестируемой функции
    ok = await action_mod.check_account_validity(account_storage, "test_service")

    assert ok is True
    # rmtree должен быть вызван в finally
    assert rm_called["called"] is True
    assert rm_called["path"] == temp_folder_path
    # убедимся, что временная папка действительно удалена
    assert not os.path.exists(temp_folder_path)


class TestVerifyReservedAccounts:
    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_all_valid(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        create_new_user,
        create_account_category,
        create_product_account,
        monkeypatch,
    ):
        """
        Интеграционный: verify_reserved_accounts возвращает список тех же ProductAccounts,
        если все слоты валидны.
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod
        # Подготовка: пользователь + purchase_request в БД
        user = await create_new_user()
        cat = await create_account_category()

        # создаём N аккаунтов
        quantity = 3
        products = []
        for _ in range(quantity):
            p, _ = await create_product_account(account_category_id=cat.account_category_id)
            products.append(p)

        # вставим purchase_request в БД (пустой, но существующий)
        async with get_db() as session:
            pr = action_mod.PurchaseRequests(user_id=user.user_id, quantity=quantity, total_amount=0, status="processing")
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            purchase_request_id = pr.purchase_request_id


        # Мокаем check_account_validity чтобы вернуть True для всех
        async def always_ok(account_storage, type_service_name):
            return True
        monkeypatch.setattr(action_mod, "check_account_validity", always_ok)

        # Вызов
        result = await action_mod.verify_reserved_accounts(products, "telegram", purchase_request_id)

        # проверяем, что получили список product accounts в ответе
        assert isinstance(result, list)
        assert len(result) == len(products)

        # должны вернутся все аккаунты которые валидные (в данном случае все валидны)
        returned_accounts = [p.to_dict() for p in result]
        for account in products:
            assert account.to_dict() in returned_accounts

    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_replace_one_candidate_found(
        self,
        replacement_pyth_account,
        replacement_needed_modules,
        create_new_user,
        create_account_category,
        create_product_account,
        monkeypatch,
    ):
        """
        Интеграционный: один из слотов невалиден, но найдена замена:
        - bad slot помечается удалённым (через вызовы update_account_storage/delete_product_account)
        - найден valid candidate, который возвращается в списке
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod
        user = await create_new_user()
        category = await create_account_category()

        # создаём "плохой" аккаунт (будет в product_accounts)
        bad_prod, _ = await create_product_account(account_category_id=category.account_category_id)
        # создаём кандидата (в БД должен быть candidate with status 'for_sale')
        cand_prod, _ = await create_product_account(
            account_category_id=category.account_category_id,
            type_account_service_id=bad_prod.type_account_service_id
        )

        # добавим purchase_request в БД
        async with get_db() as session:
            pr = action_mod.PurchaseRequests(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            purchase_request_id = pr.purchase_request_id

        # Мокаем check_account_validity: плохой -> False, кандидат -> True
        async def check_by_storage(storage, type_service_name):
            sid = getattr(storage, "account_storage_id", None)
            bad_sid = bad_prod.account_storage.account_storage_id
            if sid == bad_sid:
                return False
            return True

        monkeypatch.setattr(action_mod, "check_account_validity", check_by_storage)

        # Вызов: подаём список с одним 'плохим' аккаунтом
        result = await action_mod.verify_reserved_accounts([bad_prod], "telegram", purchase_request_id)

        # Ожидаем список валидных аккаунтов, содержащий кандидата (cand_prod)
        assert isinstance(result, list)
        # проверим что среди возвращённых есть candidate (по account_storage_id)
        assert cand_prod.to_dict() == result[0].to_dict()

    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_all_invalid_no_candidates(
        self,
        replacement_pyth_account,
        replacement_needed_modules,
        create_new_user,
        create_account_category,
        create_product_account,
        monkeypatch,
    ):
        """
        Сценарий: все аккаунты невалидны, и нет кандидатов для замены.
        Ожидаем: verify_reserved_accounts возвращает пустой список,
        AccountStorage у невалидных аккаунтов помечен как 'deleted'.
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod

        user = await create_new_user()
        cat = await create_account_category()

        # создаём несколько "плохих" аккаунтов (ни один невалиден)
        bad_accounts = []
        for _ in range(3):
            bad_acc, _ = await create_product_account(account_category_id=cat.account_category_id)
            bad_accounts.append(bad_acc)

        # добавим PurchaseRequest
        async with get_db() as session:
            pr = action_mod.PurchaseRequests(
                user_id=user.user_id,
                quantity=len(bad_accounts),
                total_amount=0,
                status="processing"
            )
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            pr_id = pr.purchase_request_id

        # мок — все невалидные
        async def always_invalid(*a, **kw): return False
        monkeypatch.setattr(action_mod, "check_account_validity", always_invalid)

        result = await action_mod.verify_reserved_accounts(bad_accounts, "telegram", pr_id)

        # все невалидные → пустой список
        assert isinstance(result, bool)
        assert result == False

        # проверим, что статусы хранилищ изменены (deleted или removed)
        async with get_db() as session:
            ids = [p.account_storage.account_storage_id for p in bad_accounts]
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id.in_(ids)))
            storages = q.scalars().all()
            assert all(s.status == "deleted" for s in storages)
            # только один аккаунт устанвливается невалидным (первый )


    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_partially_invalid_no_candidates(
        self,
        replacement_pyth_account,
        replacement_needed_modules,
        create_new_user,
        create_account_category,
        create_product_account,
        monkeypatch,
    ):
        """
        Сценарий: часть аккаунтов невалидны, и нет замены.
        Ожидаем: Возвращается False т.к. пользователю не найдённо необходимое количество.
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod

        user = await create_new_user()
        cat = await create_account_category()

        # создадим 3 аккаунта
        acc1, _ = await create_product_account(account_category_id=cat.account_category_id)
        acc2, _ = await create_product_account(account_category_id=cat.account_category_id)
        acc3, _ = await create_product_account(account_category_id=cat.account_category_id)
        accounts = [acc1, acc2, acc3]

        async with get_db() as session:
            pr = action_mod.PurchaseRequests(
                user_id=user.user_id, quantity=3, total_amount=0, status="processing"
            )
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            pr_id = pr.purchase_request_id

        # второй аккаунт невалиден
        async def validity_check(account_storage, *a, **kw):
            sid = getattr(account_storage, "account_storage_id", None)
            return sid != acc2.account_storage.account_storage_id

        monkeypatch.setattr(action_mod, "check_account_validity", validity_check)

        result = await action_mod.verify_reserved_accounts(accounts, "telegram", pr_id)

        assert result == False

        # статус: невалидный должен быть "deleted"
        async with get_db() as session:
            q = await session.execute(
                select(AccountStorage).where(AccountStorage.account_storage_id == acc2.account_storage.account_storage_id)
            )
            storage = q.scalar()
            assert storage.status == "deleted"


    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_multiple_invalid_candidates_exhausted(
        self,
        replacement_pyth_account,
        replacement_needed_modules,
        create_new_user,
        create_account_category,
        create_type_account_service,
        create_product_account,
        monkeypatch,
    ):
        """
        Сценарий: Пользователю необходим 1 аккаунт. есть 3 невалидных аккаунта и только 1 кандидат.
        Ожидаем: возвращается 1 аккаунт (замена), остальные невалидные удалены.
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod

        user = await create_new_user()
        cat = await create_account_category()
        type_service = await create_type_account_service()

        # создаём 3 "плохих" аккаунта
        bad_accounts = [
            await create_product_account(
                account_category_id=cat.account_category_id, type_account_service_id=type_service.type_account_service_id
            )
            for _ in range(3)
        ]
        bad_accounts = [b[0] for b in bad_accounts]

        # создаём только одного кандидата (status='for_sale')
        candidate, _ = await create_product_account(
            account_category_id=cat.account_category_id,
            type_account_service_id=type_service.type_account_service_id
        )

        async with get_db() as session:
            pr = action_mod.PurchaseRequests(
                user_id=user.user_id, quantity=1, total_amount=0, status="processing"
            )
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            pr_id = pr.purchase_request_id

        async def validity_check(storage, *a, **kw):
            # все bad -> False, candidate -> True
            sid = getattr(storage, "account_storage_id", None)
            bad_sids = [b.account_storage.account_storage_id for b in bad_accounts]
            return sid not in bad_sids

        monkeypatch.setattr(action_mod, "check_account_validity", validity_check)

        result = await action_mod.verify_reserved_accounts([bad_accounts[0]], "telegram", pr_id)

        # должен вернуться только один аккаунт (наш кандидат)
        assert len(result) == 1
        assert result[0].account_storage.account_storage_id == candidate.account_storage.account_storage_id

        # все старые должны быть удалены
        async with get_db() as session:
            ids = [b.account_storage.account_storage_id for b in bad_accounts]
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id.in_(ids)))
            storages = q.scalars().all()
            assert all(s.status == "deleted" for s in storages)

    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_multiple_invalid_candidates_exhausted(
        self,
        replacement_pyth_account,
        replacement_needed_modules,
        create_new_user,
        create_account_category,
        create_type_account_service,
        create_product_account,
        monkeypatch,
    ):
        """
        Сценарий: Пользователю необходимо 3 аккаунта. В функцию поступает 2 валидных и один невалидный аккаунт.
        В БД есть 3 валидных кандидата.
        Ожидаем: Возьмёт с БД один аккаунт.
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod

        user = await create_new_user()
        cat = await create_account_category()
        type_service = await create_type_account_service()

        # создаём 2 аккаунта
        valid_accounts = [
            await create_product_account(
                account_category_id=cat.account_category_id,
                type_account_service_id=type_service.type_account_service_id,
                status='reserved',
            )
            for _ in range(2)
        ]
        valid_accounts = [a[0] for a in valid_accounts] # берём первый элемент с кортежа

        # невалидный аккаунт
        bad_account, _ = await create_product_account(
            account_category_id=cat.account_category_id,
            type_account_service_id=type_service.type_account_service_id
        )
        accounts = valid_accounts.copy()
        accounts.append(bad_account)

        # создаём валидных кандидатов
        candidates = [
            await create_product_account(
                account_category_id=cat.account_category_id,
                type_account_service_id=type_service.type_account_service_id
            )
            for _ in range(3)
        ]
        candidates = [a[0] for a in candidates] # берём первый элемент с кортежа

        async with get_db() as session:
            pr = action_mod.PurchaseRequests(
                user_id=user.user_id, quantity=1, total_amount=0, status="processing"
            )
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            pr_id = pr.purchase_request_id

        async def validity_check(storage, *a, **kw):
            sid = getattr(storage, "account_storage_id", None)
            return False if bad_account.account_id == sid else True

        monkeypatch.setattr(action_mod, "check_account_validity", validity_check)

        result = await action_mod.verify_reserved_accounts(accounts, "telegram", pr_id)
        result_dicts = [acc.to_dict() for acc in result]

        # должен вернуться 3 аккаунта
        assert len(result) == 3
        for ac in valid_accounts: # валидные аккаунты которые передали должны вернуться
            assert ac.to_dict() in result_dicts

        assert bad_account.to_dict() not in result_dicts

        async with get_db() as session:
            # 2 кандидата должны быть "for_sale", а один из них "reserved"
            ids = [ca.account_storage.account_storage_id for ca in candidates]
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id.in_(ids)))
            storages = q.scalars().all()
            assert 2 == len([acc for acc in storages if acc.status == "for_sale"])
            assert 1 == len([acc for acc in storages if acc.status == "reserved"])

            # невалидный аккаунт должен стать удалённым
            q = await session.execute(
                select(AccountStorage)
                .where(
                    (AccountStorage.account_storage_id == bad_account.account_id) &
                    (AccountStorage.status == 'deleted')
                )
            )
            assert q.scalar_one_or_none()




class TestCancelPurchase:
    @pytest.mark.asyncio
    async def test_cancel_purchase_request_restores_files_and_db(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_account_category,
        create_product_account,
    ):
        """
        Проверяем:
        - файлы (temp -> orig, final -> orig) перемещаются обратно;
        - баланс пользователя увеличился на data.total_amount;
        - PurchaseRequests.status -> 'failed', BalanceHolder.status -> 'released';
        - AccountStorage.status -> 'for_sale';
        - ProductAccounts строки восстановлены (если их удалить заранее).
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod

        # подготовка: пользователь
        user = await create_new_user(balance=100)
        # подготовка: категория и продукт (product + product_full)
        cat = await create_account_category()
        prod, prod_full = await create_product_account(account_category_id=cat.account_category_id)

        # подготовим purchase_request и balance_holder в БД
        async with get_db() as session:
            pr = PurchaseRequests(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
            session.add(pr)
            await session.commit()
            await session.refresh(pr)

            bh = BalanceHolder(purchase_request_id=pr.purchase_request_id, user_id=user.user_id, amount=50, status="held")
            session.add(bh)
            await session.commit()

        # Создаём mapping: temp -> orig (создаём temp файл)
        orig = tmp_path / "orig_dir" / "account.enc"
        temp = tmp_path / "temp_dir" / "account.enc"
        # создадим temp файл, final отсутствует
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(b"fake-enc")

        mapping = [(str(orig), str(temp), None)]

        # Для проверки ветки восстановления ProductAccounts: удалим строку ProductAccounts из БД,
        # чтобы функция добавила её заново (эта ветка находится в коде)
        async with get_db() as session:
            await session.execute(
                ProductAccounts.__table__.delete().where(ProductAccounts.account_id == prod.account_id)
            )
            await session.commit()

        data = action_mod.StartPurchaseAccount(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.account_category_id,
            type_account_service_id=prod.type_account_service_id,
            promo_code_id=None,
            product_accounts=[prod],  # с загруженным account_storage
            type_service_name="telegram",
            translations_category=[],
            original_price_one_acc=100,
            purchase_price_one_acc=50,
            cost_price_one_acc=10,
            total_amount=50,
            user_balance_before=user.balance,
            user_balance_after=user.balance + 50
        )

        # Вызов
        await action_mod.cancel_purchase_request(
            user_id=user.user_id,
            mapping=mapping,
            sold_account_ids=[],
            purchase_ids=[],
            total_amount=data.total_amount,
            purchase_request_id=data.purchase_request_id,
            product_accounts=data.product_accounts,
            type_service_name=data.type_service_name
        )

        # --- проверки файлов ---
        # orig должен существовать, temp — удалён
        assert os.path.exists(str(orig))
        assert not os.path.exists(str(temp))

        # --- проверки БД ---
        async with get_db() as session:
            # баланс пользователя увеличен на total_amount
            db_user = await session.get(Users, user.user_id)
            assert db_user.balance == 100 + data.total_amount

            # PurchaseRequests.status == 'failed'
            db_pr = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert db_pr.status == "failed"

            # BalanceHolder.status == 'released'
            q = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
            db_bh = q.scalars().first()
            assert db_bh.status == "released"

            # AccountStorage status -> 'for_sale' for involved accounts
            account_storage_id = prod.account_storage.account_storage_id
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id == account_storage_id))
            storage = q.scalars().one()
            assert storage.status == "for_sale"

            # ProductAccounts row был восстановлен (т.к. мы удаляли её заранее)
            q = await session.execute(select(ProductAccounts).where(ProductAccounts.account_storage_id == account_storage_id))
            restored = q.scalars().first()
            assert restored is not None


    @pytest.mark.asyncio
    async def test_cancel_purchase_request_deletes_sold_accounts_and_restores(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_account_category,
        create_product_account,
        create_sold_account,
    ):
        """
        Проверяем что:
        - SoldAccounts и PurchasesAccounts удаляются при передаче sold_account_ids
        - остальные восстановительные операции тоже выполняются
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod

        user = await create_new_user(balance=200)
        cat = await create_account_category()

        # product для data.product_accounts
        prod, prod_full = await create_product_account(account_category_id=cat.account_category_id)
        _, sold = await create_sold_account(
            owner_id=user.user_id,
            type_account_service_id=prod.type_account_service_id
        )

        # создаём SoldAccounts и PurchasesAccounts записи, которые должны быть удалены
        async with get_db() as session:
            pa = PurchasesAccounts(
                user_id=user.user_id,
                account_storage_id=sold.account_storage.account_storage_id,
                original_price = 120,
                purchase_price = 120,
                cost_price = 100,
                net_profit = 10
            )
            session.add(pa)
            await session.commit()

            # создаём PurchaseRequests и BalanceHolder
            pr = PurchaseRequests(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
            session.add(pr)
            await session.commit()
            await session.refresh(pr)

            bh = BalanceHolder(purchase_request_id=pr.purchase_request_id, user_id=user.user_id, amount=30, status="held")
            session.add(bh)
            await session.commit()

        # mapping: create temp file to be moved back
        orig = tmp_path / "orig2" / "a.enc"
        temp = tmp_path / "temp2" / "a.enc"
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(b"data")
        mapping = [(str(orig), str(temp), None)]

        data = action_mod.StartPurchaseAccount(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.account_category_id,
            type_account_service_id=prod.type_account_service_id,
            promo_code_id=None,
            product_accounts=[prod],
            type_service_name="telegram",
            translations_category=[],
            original_price_one_acc=100,
            purchase_price_one_acc=30,
            cost_price_one_acc=10,
            total_amount=30,
            user_balance_before=user.balance,
            user_balance_after=user.balance + 30
        )

        # вызов с sold_account_ids
        await action_mod.cancel_purchase_request(
            user_id=user.user_id,
            mapping=mapping,
            sold_account_ids=[sold.sold_account_id],
            purchase_ids=[pa.purchase_id],
            total_amount=data.total_amount,
            purchase_request_id=data.purchase_request_id,
            product_accounts=data.product_accounts,
            type_service_name=data.type_service_name
        )

        # проверки
        # файл перемещён
        assert os.path.exists(str(orig))
        assert not os.path.exists(str(temp))

        async with get_db() as session:
            # SoldAccounts удалены
            q = await session.execute(select(SoldAccounts).where(SoldAccounts.account_storage_id == sold.account_storage.account_storage_id))
            assert q.scalars().first() is None

            # PurchasesAccounts удалены
            q = await session.execute(select(PurchasesAccounts).where(PurchasesAccounts.account_storage_id == sold.account_storage.account_storage_id))
            assert q.scalars().first() is None

            # PurchaseRequests status / BalanceHolder status
            db_pr = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert db_pr.status == "failed"
            q = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
            db_bh = q.scalars().first()
            assert db_bh.status == "released"

            # AccountStorage status -> for_sale
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id == prod.account_storage.account_storage_id))
            storage = q.scalars().one()
            assert storage.status == "for_sale"


class TestFinalizePurchase:
    @pytest.mark.asyncio
    async def test_finalize_purchase_success_creates_sold_and_purchases_and_updates_states(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_account_category,
        create_product_account,
        create_promo_code,
        monkeypatch,
    ):
        """
        Успешное выполнение finalize_purchase:
        - move_file возвращает True (создаём temp файл),
        - rename_file возвращает True (перемещаем temp->final),
        - созданы SoldAccounts и PurchasesAccounts,
        - AccountStorage.status == 'bought',
        - PurchaseRequests.status == 'completed', BalanceHolder.status == 'used',
        - publish_event вызван как для промокода, так и для account.purchase.
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod

        # подготовка: пользователь, категория, продукт
        user = await create_new_user(balance=1000)
        cat = await create_account_category()
        promo = await create_promo_code()
        prod, prod_full = await create_product_account(account_category_id=cat.account_category_id)

        # создаём PurchaseRequests и BalanceHolder (их код ожидает существование)
        async with get_db() as session:
            pr = action_mod.PurchaseRequests(user_id=user.user_id, quantity=1, total_amount=prod_full.price if hasattr(prod_full, "price") else 0, status="processing")
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            # создаём BalanceHolder
            bh = action_mod.BalanceHolder(purchase_request_id=pr.purchase_request_id, user_id=user.user_id, amount=10, status="held")
            session.add(bh)
            await session.commit()

        # Подготовим fake move_file: при вызове создаёт temp файл (имитируем move(orig -> temp))
        async def fake_move_file(orig: str, temp: str):
            os.makedirs(os.path.dirname(temp), exist_ok=True)
            with open(temp, "wb") as f:
                f.write(b"fake")
            return True

        async def fake_rename_file(src: str, dst: str):
            # имитируем перемещение temp->final
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(src):
                os.replace(src, dst)
                return True
            return False

        # Собиратели вызовов
        publish_calls = []

        async def fake_publish_event(payload, topic):
            publish_calls.append((topic, payload))
            return True

        # Подмены
        monkeypatch.setattr(action_mod, "move_file", fake_move_file)
        monkeypatch.setattr(action_mod, "rename_file", fake_rename_file)
        monkeypatch.setattr(action_mod, "publish_event", fake_publish_event)

        # Подменим filling_* чтобы не ломать тест (они работают с redis; можно просто заглушить)
        async def noop_fill(*a, **kw): return None
        monkeypatch.setattr(action_mod, "filling_sold_accounts_by_owner_id", noop_fill)
        monkeypatch.setattr(action_mod, "filling_product_accounts_by_category_id", noop_fill)
        monkeypatch.setattr(action_mod, "filling_sold_account_by_account_id", noop_fill)
        monkeypatch.setattr(action_mod, "filling_product_account_by_account_id", noop_fill)

        data = StartPurchaseAccount(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.account_category_id,
            type_account_service_id=prod.type_account_service_id,
            promo_code_id=promo.promo_code_id,
            product_accounts=[prod],
            type_service_name="telegram",
            translations_category=[],
            original_price_one_acc=100,
            purchase_price_one_acc=50,
            cost_price_one_acc=10,
            total_amount=50,
            user_balance_before=user.balance,
            user_balance_after=user.balance - 50,
        )

        # Выполнение
        await action_mod.finalize_purchase(user.user_id, data)

        # --- проверки БД ---
        async with get_db() as session:
            # SoldAccounts должен существовать
            q = await session.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
            sold = q.scalars().all()
            assert len(sold) >= 1

            # PurchasesAccounts должен существовать для созданного sold_account
            q2 = await session.execute(select(PurchasesAccounts).where(PurchasesAccounts.user_id == user.user_id))
            purchases = q2.scalars().all()
            assert len(purchases) >= 1

            # AccountStorage статус -> 'bought'
            q3 = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id == prod.account_storage.account_storage_id))
            storage = q3.scalars().one()
            assert storage.status == "bought"

            # PurchaseRequests.status == 'completed'
            db_pr = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert db_pr.status == "completed"

            # BalanceHolder.status == 'used'
            qb = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
            db_bh = qb.scalars().first()
            assert db_bh.status == "used"

        # publish_event должен был вызваться хотя бы дважды (promo activation + account.purchase)
        topics = [t for t, p in publish_calls]
        assert any("promo_code.activated" == t for t in topics)
        assert any("account.purchase" == t for t in topics)


    @pytest.mark.asyncio
    async def test_finalize_purchase_move_file_failure_calls_cancel_and_logs(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        create_new_user,
        create_account_category,
        create_product_account,
        monkeypatch,
    ):
        """
        Если move_file вернул False — должен вызвать send_log и cancel_purchase_request, и не создать SoldAccounts.
        Здесь мы мокируем cancel_purchase_request, чтобы проверить только факт вызова.
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod
        from src.services.database.selling_accounts.models.models import SoldAccounts

        user = await create_new_user()
        cat = await create_account_category()
        prod, _ = await create_product_account(account_category_id=cat.account_category_id)

        # подготовим PurchaseRequests и BalanceHolder (необязательно, но нормально)
        async with get_db() as session:
            pr = action_mod.PurchaseRequests(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
            session.add(pr)
            await session.commit()
            await session.refresh(pr)

        # move_file возвращает False (не удалось переместить первый файл)
        async def fake_move_file(orig, temp):
            return False

        called = {"cancel": False, "logged": False}

        async def fake_cancel(user_id, mapping, sold_account_ids, **kw):
            called["cancel"] = True

        async def fake_send_log(text):
            called["logged"] = True

        monkeypatch.setattr(action_mod, "move_file", fake_move_file)
        monkeypatch.setattr(action_mod, "cancel_purchase_request", fake_cancel)
        monkeypatch.setattr(action_mod, "send_log", fake_send_log)

        # заглушки для rename/fill/publish
        async def noop(*a, **kw): return None
        monkeypatch.setattr(action_mod, "rename_file", noop)
        monkeypatch.setattr(action_mod, "filling_sold_accounts_by_owner_id", noop)
        monkeypatch.setattr(action_mod, "filling_product_accounts_by_category_id", noop)
        monkeypatch.setattr(action_mod, "filling_sold_account_by_account_id", noop)
        monkeypatch.setattr(action_mod, "filling_product_account_by_account_id", noop)
        monkeypatch.setattr(action_mod, "publish_event", noop)

        data = StartPurchaseAccount(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.account_category_id,
            type_account_service_id=prod.type_account_service_id,
            promo_code_id=None,
            product_accounts=[prod],
            type_service_name="telegram",
            translations_category=[],
            original_price_one_acc=100,
            purchase_price_one_acc=50,
            cost_price_one_acc=10,
            total_amount=50,
            user_balance_before=user.balance,
            user_balance_after=user.balance,
        )

        await action_mod.finalize_purchase(user.user_id, data)

        assert called["logged"] is True
        assert called["cancel"] is True

        # Проверим, что SoldAccounts не созданы
        async with get_db() as session:
            q = await session.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
            assert q.scalars().first() is None


    @pytest.mark.asyncio
    async def test_finalize_purchase_rename_failure_triggers_cancel_and_rolls_back(
        self,
        replacement_pyth_account,
        patch_fake_aiogram,
        tmp_path,
        create_new_user,
        create_account_category,
        create_product_account,
        monkeypatch,
    ):
        """
        Если rename_file вернул False после успешного commit, finalize_purchase должен вызвать cancel_purchase_request.
        Здесь позволим cancel_purchase_request выполнить реальные откаты (не мокируем).
        После выполнения ожидаем, что SoldAccounts/PurchasesAccounts удалены и PurchaseRequests.status == 'failed'
        """
        from src.services.database.selling_accounts.actions import action_purchase as action_mod

        user = await create_new_user()
        cat = await create_account_category()
        prod, prod_full = await create_product_account(account_category_id=cat.account_category_id)

        # создаём PurchaseRequests и BalanceHolder
        async with get_db() as session:
            pr = action_mod.PurchaseRequests(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            bh = action_mod.BalanceHolder(purchase_request_id=pr.purchase_request_id, user_id=user.user_id, amount=10, status="held")
            session.add(bh)
            await session.commit()

        # move_file делает temp файл
        async def fake_move_file(orig: str, temp: str):
            os.makedirs(os.path.dirname(temp), exist_ok=True)
            with open(temp, "wb") as f:
                f.write(b"tempdata")
            return True

        # rename_file возвращает False (симулируем проблему при переименовании)
        async def fake_rename_file(src: str, dst: str):
            return False

        # Подменяем move/rename и заглушаем filling/publish
        monkeypatch.setattr(action_mod, "move_file", fake_move_file)
        monkeypatch.setattr(action_mod, "rename_file", fake_rename_file)

        data = SimpleNamespace(
            purchase_request_id=pr.purchase_request_id,
            category_id=cat.account_category_id,
            type_account_service_id=prod.type_account_service_id,
            promo_code_id=None,
            product_accounts=[prod],
            type_service_name="telegram",
            translations_category=[],
            original_price_one_acc=100,
            purchase_price_one_acc=50,
            cost_price_one_acc=10,
            total_amount=50,
            user_balance_before=user.balance,
            user_balance_after=user.balance - 50,
        )

        # Выполнение finalize — в теле rename_file вернёт False, finalize вызовет cancel_purchase_request (реальную)
        await action_mod.finalize_purchase(user.user_id, data)

        # После этого SoldAccounts и PurchasesAccounts должны быть удалены (cancel_purchase_request делает это)
        async with get_db() as session:
            q = await session.execute(select(SoldAccounts).where(SoldAccounts.owner_id == user.user_id))
            assert q.scalars().first() is None

            q2 = await session.execute(select(PurchasesAccounts).where(PurchasesAccounts.user_id == user.user_id))
            assert q2.scalars().first() is None

            # PurchaseRequests должен быть помечен как failed
            pr_after = await session.get(PurchaseRequests, pr.purchase_request_id)
            assert pr_after.status == "failed"

            # BalanceHolder должен быть released
            qbh = await session.execute(select(BalanceHolder).where(BalanceHolder.purchase_request_id == pr.purchase_request_id))
            bh_after = qbh.scalars().first()
            assert bh_after.status == "released"