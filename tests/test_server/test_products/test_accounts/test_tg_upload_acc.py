import os

import pytest


@pytest.mark.asyncio
async def test_upload_tg_account_chunks(monkeypatch, create_product_account, tmp_path):
    from src.services.products.accounts.tg.upload_account import upload_tg_account

    # создаём реальные аккаунты через фикстуру
    accounts = []
    for _ in range(5):
        _, acc = await create_product_account()
        accounts.append(acc)


    async def fake_get_storage(category_id):
        return accounts

    def fake_get_dir_size(path: str):
        return 20 * 1024 * 1024 # 20 мб

    from src.services.products.accounts.tg import upload_account as modul
    monkeypatch.setattr(modul, "get_account_storage_by_category_id",fake_get_storage)
    monkeypatch.setattr(modul, "get_dir_size",fake_get_dir_size)

    # запускаем функцию и анализируем выходные ZIP-файлы
    yielded = []
    async for archive_path in upload_tg_account(category_id=1):
        yielded.append(archive_path)

        # zip-файл ДОЛЖЕН существовать в момент yield
        assert os.path.exists(archive_path)

    # теперь zip-файлы должны быть удалены
    for p in yielded:
        assert not os.path.exists(p), f"{p} должен быть удалён после yield!"


    assert len(yielded) == 3, "Должно быть 3 чанка"
