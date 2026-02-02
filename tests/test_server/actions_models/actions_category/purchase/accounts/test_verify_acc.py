import os
import shutil
from pathlib import Path

import pytest
from sqlalchemy import select

from src.services.database.categories.models import AccountStorage, StorageStatus
from src.services.database.categories.models import AccountServiceType
from src.services.database.core import get_db


@pytest.mark.asyncio
async def test_check_account_validity_async_success(
    patch_fake_aiogram,
    create_product_account,
    create_category,
    monkeypatch,
):
    """
    Unit: check_account_validity должен:
    - вызвать decryption_tg_account (мы мокаем),
    - вызвать check_valid_accounts_telethon (мокаем) и вернуть True,
    - вызвать shutil.rmtree в finally (мокаем).
    """
    from src.services.products.accounts.tg import actions
    from src.services.products.accounts.tg.actions import check_account_validity

    # создаём тестовую категорию и продукт (этот шаг даёт нам AccountStorage)
    cat = await create_category()
    prod_obj, _ = await create_product_account(category_id=cat.category_id)

    account_storage = prod_obj.account_storage

    # СДЕЛАЕМ decryption синхронным (то, что ожидает asyncio.to_thread)
    temp_folder_path = Path.cwd() / "tmp_test_account_folder"

    def fake_decryption_tg_account(account_storage_arg, kek, *args, **kwargs):
        # создаём папку, чтобы rmtree мог ее удалить (проверим вызов)
        os.makedirs(temp_folder_path, exist_ok=True)
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
    ok = await check_account_validity(account_storage, AccountServiceType.TELEGRAM, status=account_storage.status)

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
        patch_fake_aiogram,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Интеграционный: verify_reserved_accounts возвращает список тех же ProductAccounts,
        если все слоты валидны.
        """
        from src.services.database.categories.actions.purchases.accounts import verify as verify_mod
        from src.services.database.categories.actions.purchases.accounts.verify import verify_reserved_accounts
        # Подготовка: пользователь + purchase_request в БД
        cat = await create_category()

        # создаём N аккаунтов
        quantity = 3
        products = []
        for _ in range(quantity):
            p, _ = await create_product_account(category_id=cat.category_id)
            products.append(p)

        # вставим purchase_request в БД (пустой, но существующий)
        pr = await create_purchase_request(quantity=quantity, total_amount=0, status="processing")
        purchase_request_id = pr.purchase_request_id


        # Мокаем check_account_validity чтобы вернуть True для всех
        async def always_ok(account_storage, type_service_account, *args, **kwargs):
            return True
        monkeypatch.setattr(verify_mod, "check_account_validity", always_ok)

        # Вызов
        result = await verify_reserved_accounts(products, cat.type_account_service, purchase_request_id)

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
        replacement_needed_modules,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Интеграционный: один из слотов невалиден, но найдена замена:
        - bad slot помечается удалённым (через вызовы update_account_storage/delete_product_account)
        - найден valid candidate, который возвращается в списке
        """
        from src.services.database.categories.actions.purchases.accounts import verify as verify_mod
        from src.services.database.categories.actions.purchases.accounts.verify import verify_reserved_accounts
        user = await create_new_user()
        category = await create_category()

        # создаём "плохой" аккаунт (будет в product_accounts)
        bad_prod, _ = await create_product_account(category_id=category.category_id)
        # создаём кандидата (в БД должен быть candidate with status 'for_sale')
        cand_prod, _ = await create_product_account(
            category_id=category.category_id,
            type_account_service=bad_prod.account_storage.type_account_service
        )

        # добавим purchase_request в БД

        pr = await create_purchase_request(user_id=user.user_id, quantity=1, total_amount=0)
        purchase_request_id = pr.purchase_request_id

        # Мокаем check_account_validity: плохой -> False, кандидат -> True
        async def check_by_storage(storage, type_service_account, *args, **kwargs):
            sid = getattr(storage, "account_storage_id", None)
            bad_sid = bad_prod.account_storage.account_storage_id
            if sid == bad_sid:
                return False
            return True

        monkeypatch.setattr(verify_mod, "check_account_validity", check_by_storage)

        # Вызов: подаём список с одним 'плохим' аккаунтом
        result = await verify_reserved_accounts(
            [bad_prod], bad_prod.account_storage.type_account_service , purchase_request_id
        )

        # Ожидаем список валидных аккаунтов, содержащий кандидата (cand_prod)
        assert isinstance(result, list)
        # проверим что среди возвращённых есть candidate (по account_storage_id)
        assert cand_prod.to_dict() == result[0].to_dict()


    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_all_invalid_no_candidates(
        self,
        replacement_needed_modules,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Сценарий: все аккаунты невалидны, и нет кандидатов для замены.
        Ожидаем: verify_reserved_accounts возвращает пустой список,
        AccountStorage у невалидных аккаунтов помечен как 'deleted'.
        """
        from src.services.database.categories.actions.purchases.accounts import verify as verify_mod
        from src.services.database.categories.actions.purchases.accounts.verify import verify_reserved_accounts

        user = await create_new_user()
        cat = await create_category()

        # создаём несколько "плохих" аккаунтов (ни один невалиден)
        bad_accounts = []
        for _ in range(3):
            bad_acc, _ = await create_product_account(category_id=cat.category_id)
            bad_accounts.append(bad_acc)

        # добавим PurchaseRequest

        pr = await create_purchase_request(
            user_id=user.user_id,
            quantity=len(bad_accounts),
            total_amount=0,
            status="processing"
        )
        pr_id = pr.purchase_request_id

        # мок — все невалидные
        async def always_invalid(*a, **kw): return False
        monkeypatch.setattr(verify_mod, "check_account_validity", always_invalid)

        result = await verify_reserved_accounts(bad_accounts, cat.type_account_service, pr_id)

        # все невалидные → пустой список
        assert isinstance(result, bool)
        assert result == False

        # проверим, что статусы хранилищ изменены (deleted или removed)
        async with get_db() as session:
            ids = [p.account_storage.account_storage_id for p in bad_accounts]
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id.in_(ids)))
            storages = q.scalars().all()
            assert all(s.status == StorageStatus.DELETED for s in storages)
            # только один аккаунт устанвливается невалидным (первый )


    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_partially_invalid_no_candidates(
        self,
        replacement_needed_modules,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Сценарий: часть аккаунтов невалидны, и нет замены.
        Ожидаем: Возвращается False т.к. пользователю не найдённо необходимое количество.
        """
        from src.services.database.categories.actions.purchases.accounts import verify as verify_mod
        from src.services.database.categories.actions.purchases.accounts.verify import verify_reserved_accounts

        user = await create_new_user()
        cat = await create_category()

        # создадим 3 аккаунта
        acc1, acc1_full = await create_product_account(category_id=cat.category_id, status=StorageStatus.RESERVED)
        acc2, acc2_full = await create_product_account(category_id=cat.category_id, status=StorageStatus.RESERVED)
        acc3, acc3_full = await create_product_account(category_id=cat.category_id, status=StorageStatus.RESERVED)
        accounts = [acc1, acc2, acc3]

        pr = await create_purchase_request(user_id=user.user_id, quantity=3, total_amount=0, status="processing")
        pr_id = pr.purchase_request_id

        # второй аккаунт невалиден
        async def validity_check(account_storage, *a, **kw):
            sid = getattr(account_storage, "account_storage_id", None)
            return sid != acc2.account_storage.account_storage_id

        monkeypatch.setattr(verify_mod, "check_account_validity", validity_check)

        result = await verify_reserved_accounts(accounts, acc1_full.account_storage.type_account_service, pr_id)

        assert result == False

        # статус: невалидный должен быть "deleted"
        async with get_db() as session:
            q = await session.execute(
                select(AccountStorage)
                .where(AccountStorage.account_storage_id == acc2_full.account_storage.account_storage_id)
            )
            storage = q.scalar()
            assert storage.status == StorageStatus.DELETED


    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_multiple_invalid_candidates_exhausted_1(
        self,
        replacement_needed_modules,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Сценарий: Пользователю необходим 1 аккаунт. есть 3 невалидных аккаунта и только 1 кандидат.
        Ожидаем: возвращается 1 аккаунт (замена), остальные невалидные удалены.
        """
        from src.services.database.categories.actions.purchases.accounts import verify as verify_mod
        from src.services.database.categories.actions.purchases.accounts.verify import verify_reserved_accounts

        user = await create_new_user()
        cat = await create_category()

        # создаём 3 "плохих" аккаунта
        bad_accounts = [
            await create_product_account(
                category_id=cat.category_id, type_account_service=AccountServiceType.TELEGRAM
            )
            for _ in range(3)
        ]
        _, first_acc = bad_accounts[0]
        type_account_service = first_acc.account_storage.type_account_service

        bad_accounts = [b[0] for b in bad_accounts]

        # создаём только одного кандидата (status='for_sale')
        candidate, _ = await create_product_account(
            category_id=cat.category_id,
            type_account_service=AccountServiceType.TELEGRAM
        )

        pr = await create_purchase_request(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
        pr_id = pr.purchase_request_id

        async def validity_check(storage, *a, **kw):
            # все bad -> False, candidate -> True
            sid = getattr(storage, "account_storage_id", None)
            bad_sids = [b.account_storage.account_storage_id for b in bad_accounts]
            return sid not in bad_sids

        monkeypatch.setattr(verify_mod, "check_account_validity", validity_check)

        result = await verify_reserved_accounts(
            [bad_accounts[0]],
            type_account_service,
            pr_id
        )

        # должен вернуться только один аккаунт (наш кандидат)
        assert len(result) == 1
        assert result[0].account_storage.account_storage_id == candidate.account_storage.account_storage_id

        # все старые должны быть удалены
        async with get_db() as session:
            ids = [b.account_storage.account_storage_id for b in bad_accounts]
            q = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id.in_(ids)))
            storages = q.scalars().all()
            assert all(s.status == StorageStatus.DELETED for s in storages)


    @pytest.mark.asyncio
    async def test_verify_reserved_accounts_multiple_invalid_candidates_exhausted_2(
        self,
        replacement_needed_modules,
        create_new_user,
        create_category,
        create_product_account,
        create_purchase_request,
        monkeypatch,
    ):
        """
        Сценарий: Пользователю необходимо 3 аккаунта. В функцию поступает 2 валидных и один невалидный аккаунт.
        В БД есть 3 валидных кандидата.
        Ожидаем: Возьмёт с БД один аккаунт.
        """
        from src.services.database.categories.actions.purchases.accounts import verify as verify_mod
        from src.services.database.categories.actions.purchases.accounts.verify import verify_reserved_accounts

        user = await create_new_user()
        cat = await create_category()

        # создаём 2 аккаунта
        valid_accounts = [
            await create_product_account(
                category_id=cat.category_id,
                type_account_service=AccountServiceType.TELEGRAM,
                status=StorageStatus.RESERVED,
            )
            for _ in range(2)
        ]
        valid_accounts = [a[0] for a in valid_accounts] # берём первый элемент с кортежа

        # невалидный аккаунт
        bad_account, _ = await create_product_account(
            category_id=cat.category_id,
            type_account_service=AccountServiceType.TELEGRAM
        )
        accounts = valid_accounts.copy()
        accounts.append(bad_account)

        # создаём валидных кандидатов
        candidates = [
            await create_product_account(
                category_id=cat.category_id,
                type_account_service=AccountServiceType.TELEGRAM
            )
            for _ in range(3)
        ]
        candidates = [a[0] for a in candidates] # берём первый элемент с кортежа

        pr = await create_purchase_request(user_id=user.user_id, quantity=1, total_amount=0, status="processing")
        pr_id = pr.purchase_request_id

        async def validity_check(storage, *a, **kw):
            sid = getattr(storage, "account_storage_id", None)
            return False if bad_account.account_id == sid else True

        monkeypatch.setattr(verify_mod, "check_account_validity", validity_check)

        result = await verify_reserved_accounts(accounts, AccountServiceType.TELEGRAM, pr_id)
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
            assert 2 == len([acc for acc in storages if acc.status == StorageStatus.FOR_SALE])
            assert 1 == len([acc for acc in storages if acc.status == StorageStatus.RESERVED])

            # невалидный аккаунт должен стать удалённым
            q = await session.execute(
                select(AccountStorage)
                .where(
                    (AccountStorage.account_storage_id == bad_account.account_id) &
                    (AccountStorage.status == StorageStatus.DELETED)
                )
            )
            assert q.scalar_one_or_none()
