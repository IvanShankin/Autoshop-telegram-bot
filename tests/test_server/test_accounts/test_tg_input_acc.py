import zipfile
from copy import copy

import pytest
from unittest.mock import patch, AsyncMock
from pathlib import Path

from sqlalchemy import select
from telethon.hints import Phone

from src.exceptions import ArchiveNotFount, DirNotFount
from src.services.database.core import get_db
from types import SimpleNamespace

from src.services.accounts.tg.shemas import BaseAccountProcessingResult, ArchiveProcessingResult
from telethon.tl.types import User
from src.services.database.selling_accounts.models import ProductAccounts


VALID_USER = User(
    id=1,
    first_name="Test",
    last_name="",
    username="",
    phone="123",
    status=None,
    photo=None,
    bot=False,
    deleted=False,
    restricted=False,
    verified=False,
    support=False,
    scam=False,
    fake=False,
    lang_code=None
)
# при изменении данного объекта использовать его копию!
# ибо получаем его по ссылке


class TestImportAccount:
    @pytest.mark.asyncio
    async def test_import_creates_product_account(self, tmp_path, create_account_category):
        """
        Интеграционный тест:
        - создаёт входной zip с двумя директориями acc1 и acc2 (каждая содержит tdata + session.session)
        - мокает check_valid_accounts_telethon: acc1 -> user1, acc2 -> user2 (разные id/phone)
        - запускает import_telegram_accounts_from_archive
        - ожидает ImportResult и затем проверяет, что в БД появился ProductAccounts
        """
        from src.services.accounts.tg.input_account import import_telegram_accounts_from_archive

        # подготовка: создаём две директории acc1 и acc2 с минимальной структурой
        work_dir = tmp_path / "work"
        acc1 = work_dir / "acc1"
        acc2 = work_dir / "acc2"
        for d in (acc1, acc2):
            tdata = d / "tdata"
            tdata.mkdir(parents=True, exist_ok=True)
            # создаём пустой session.session (т.к. проверка будет мокнута, достаточно файла)
            (d / "session.session").write_text("session")
            # добавим какой-то файл в tdata чтобы zip был не пуст
            (tdata / "info.txt").write_text("ok")

        # архивируем acc1/acc2 в один входной zip
        input_zip = tmp_path / "input_accounts.zip"
        with zipfile.ZipFile(input_zip, "w") as z:
            # пишем директории с относительными путями
            for d in [acc1, acc2]:
                for p in d.rglob("*"):
                    arcname = str(p.relative_to(work_dir))
                    z.write(p, arcname=arcname)

        # создаём копии VALID_USER с разными id/phones
        user1 = copy(VALID_USER)
        user1.id = 101
        user1.phone = "1001"

        user2 = copy(VALID_USER)
        user2.id = 102
        user2.phone = "1002"

        # side_effect для мокнутой проверки: смотрим на dir path и возвращаем user1/user2
        async def fake_check(path):
            s = str(path)
            if "acc1" in s:
                return user1
            if "acc2" in s:
                return user2
            return None

        # создаём категорию (фигстура)
        category = await create_account_category(is_accounts_storage=True)

        # запускаем интеграционный импорт (мок только проверки валидности)
        with patch("src.services.accounts.tg.input_account.check_valid_accounts_telethon", new=AsyncMock(side_effect=fake_check)):
            gen = import_telegram_accounts_from_archive(str(input_zip), account_category_id=category.account_category_id, type_account_service="telegram")

            # получаем результат (он yield-ит ImportResult)
            result = await gen.__anext__()

            # ДО того, как закроем генератор — проверяем, что он вернул ожидаемые поля
            assert result.total_processed == 2
            # invalid и duplicate могут быть None
            assert hasattr(result, "invalid_archive_path")
            assert hasattr(result, "duplicate_archive_path")

            # завершить генератор, чтобы заработал cleanup (внутри import_telegram... после yield)
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        # проверяем, что в БД создался ProductAccounts (связка аккаунта с категорией)
        async with get_db() as session_db:
            res = await session_db.execute(select(ProductAccounts))
            prod = res.scalars().first()
            assert prod is not None, "Ожидались записи в ProductAccounts после импорта"


    @pytest.mark.asyncio
    async def test_import_with_duplicate_accounts_archived(self, tmp_path, create_account_category):
        """
        Интеграционный тест на дубликаты:
        - создаём два accX директории, но оба возвращают одного и того же user (одинаковый id/phone)
        - импорт должен поместить один уникальный в БД, а второй — в duplicate_dir (архив)
        - проверяем, что duplicate_archive_path в результате не None и что в БД только один ProductAccounts
        """
        from src.services.accounts.tg.input_account import import_telegram_accounts_from_archive

        work_dir = tmp_path / "work_dup"
        acc1 = work_dir / "acc1"
        acc2 = work_dir / "acc2"
        for d in (acc1, acc2):
            tdata = d / "tdata"
            tdata.mkdir(parents=True, exist_ok=True)
            (d / "session.session").write_text("session")
            (tdata / "info.txt").write_text("ok")

        input_zip = tmp_path / "dup_input.zip"
        with zipfile.ZipFile(input_zip, "w") as z:
            for d in [acc1, acc2]:
                for p in d.rglob("*"):
                    arcname = str(p.relative_to(work_dir))
                    z.write(p, arcname=arcname)

        # оба раза возвращаем одинакового пользователя (идентичен VALID_USER копии)
        dup_user = VALID_USER

        async def fake_check_dup(path):
            return dup_user

        category = await create_account_category(is_accounts_storage=True)

        with patch("src.services.accounts.tg.input_account.check_valid_accounts_telethon", new=AsyncMock(side_effect=fake_check_dup)):
            gen = import_telegram_accounts_from_archive(str(input_zip), account_category_id=category.account_category_id, type_account_service="telegram")
            result = await gen.__anext__()

            # должно быть два обработанных, но один дубликат -> duplicate_archive_path не None
            assert result.total_processed == 2
            assert result.duplicate_archive_path is not None

            # важно: перед тем как завершить генератор проверим, что duplicate_archive_path указывает на файл
            dup_path = result.duplicate_archive_path
            assert Path(dup_path).exists()

            # завершаем генератор (запустит cleanup)
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        # В БД должна быть ровно одна запись ProductAccounts (так как один уникальный)
        async with get_db() as session_db:
            res = await session_db.execute(select(ProductAccounts))
            items = res.scalars().all()
            assert len(items) == 1

    @pytest.mark.asyncio
    async def test_import_with_invalid_accounts_archived(self, tmp_path, create_account_category):
        """
        Интеграционный тест:
        - создаём одну директорию acc_bad
        - мок check_valid_accounts_telethon -> всегда None (невалидный)
        - импорт должен поместить её в invalid_dir и создать invalid_archive_path
        - duplicate_archive_path должен быть None
        - в БД не должно быть ни одного ProductAccounts
        """
        from src.services.accounts.tg.input_account import import_telegram_accounts_from_archive

        work_dir = tmp_path / "work_invalid"
        acc_bad = work_dir / "acc_bad"
        tdata = acc_bad / "tdata"
        tdata.mkdir(parents=True, exist_ok=True)
        (acc_bad / "session.session").write_text("session")
        (tdata / "info.txt").write_text("ok")

        # создаём ZIP
        input_zip = tmp_path / "invalid_input.zip"
        with zipfile.ZipFile(input_zip, "w") as z:
            for p in acc_bad.rglob("*"):
                z.write(p, p.relative_to(work_dir))

        # Мокаем проверку → всегда НЕВАЛИДНЫЙ
        async def fake_check_invalid(path):
            return None

        category = await create_account_category(is_accounts_storage=True)

        with patch(
                "src.services.accounts.tg.input_account.check_valid_accounts_telethon",
                new=AsyncMock(side_effect=fake_check_invalid),
        ):
            gen = import_telegram_accounts_from_archive(
                str(input_zip),
                account_category_id=category.account_category_id,
                type_account_service="telegram"
            )

            result = await gen.__anext__()

            # 1 обработанный, все невалидные
            assert result.total_processed == 1
            assert result.invalid_archive_path is not None, "invalid_archive_path должен быть создан!"
            assert result.duplicate_archive_path is None

            # файл invalid.zip должен существовать
            invalid_path = Path(result.invalid_archive_path)
            assert invalid_path.exists(), "invalid.zip должен быть создан!"

            # завершаем генератор (cleanup)
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        # В БД не должно быть добавлено ни одного ProductAccounts
        async with get_db() as session_db:
            res = await session_db.execute(select(ProductAccounts))
            items = res.scalars().all()
            assert len(items) == 0, "Не должно быть ProductAccounts для невалидных данных"

@pytest.mark.asyncio
async def test_import_in_db_valid_and_invalid(tmp_path, create_account_category):
    from src.services.accounts.tg.input_account import import_in_db
    # Создаём валидный и битый item
    category = await create_account_category(is_accounts_storage=True)
    valid_item = BaseAccountProcessingResult(valid=True, dir_path=str(tmp_path / "valid_acc"), user= VALID_USER)

    invalid_item = BaseAccountProcessingResult(valid=True, dir_path=str(tmp_path / "invalid_acc"), user=VALID_USER)
    Path(valid_item.dir_path).mkdir()
    Path(invalid_item.dir_path).mkdir()

    # Моки DB и файлов
    with patch("src.services.accounts.tg.input_account.encrypted_tg_account", new_callable=AsyncMock) as mock_enc, \
            patch("src.services.accounts.tg.input_account.make_archive", new_callable=AsyncMock) as mock_make_archive:
        # Настроим шифрование: первый успех, второй провал
        mock_enc.side_effect = [
            SimpleNamespace(result=True, encrypted_key_b64="k", encrypted_key_nonce="fsdvxfsd", checksum="c"),
            SimpleNamespace(result=False)
        ]

        await import_in_db(
            [valid_item, invalid_item],
            "telegram",
            str(tmp_path / "invalid_dir"),
            category.account_category_id
        )
        copied_dir = Path(tmp_path / "invalid_dir") / Path(invalid_item.dir_path).name
        archive_file = str(copied_dir.with_suffix(".zip"))

        mock_make_archive.assert_called_once_with(str(copied_dir), archive_file)

        async with get_db() as session_db:
            result_db = await session_db.execute(select(ProductAccounts))
            acc = result_db.scalars().first()
            assert acc


async def test_split_unique_and_duplicates_basic(create_type_account_service):
    from src.services.accounts.tg.input_account import split_unique_and_duplicates

    type_service = await create_type_account_service()

    user_1 = VALID_USER
    user_2 = copy(VALID_USER)
    user_3 = VALID_USER
    user_2.phone="222"
    user_2.id=2

    items = [
        BaseAccountProcessingResult(valid=True, user=user_1, phone="123", dir_path="a"),
        BaseAccountProcessingResult(valid=True, user=user_2, phone="12345", dir_path="b"),
        BaseAccountProcessingResult(valid=True, user=user_3, phone="123456789", dir_path="c"),  # дубликат
    ]

    unique, duplicates, invalid = await split_unique_and_duplicates(items, type_service.name)
    assert len(unique) == 2
    assert len(duplicates) == 1
    assert duplicates[0].dir_path == "c"


@pytest.mark.asyncio
async def test_process_duplicates_calls_make_archive(tmp_path):
    from src.services.accounts.tg.input_account import process_inappropriate_acc
    items = [SimpleNamespace(dir_path=str(tmp_path / f"dup{i}")) for i in range(2)]
    for item in items:
        Path(item.dir_path).mkdir()

    with patch("src.services.accounts.tg.input_account.make_archive", new_callable=AsyncMock) as mock_make:
        await process_inappropriate_acc(items, str(tmp_path / "dup_dir"))
        assert mock_make.call_count == 2


@pytest.mark.asyncio
async def test_process_archives_batch_no_archives(tmp_path):
    from src.services.accounts.tg.input_account import process_archives_batch
    with pytest.raises(ArchiveNotFount):
        await process_archives_batch(str(tmp_path))


@pytest.mark.asyncio
async def test_process_archives_batch_calls_process_single_archive(tmp_path):
    from src.services.accounts.tg.input_account import process_archives_batch
    # создаём "архив" (пусть пустой файл zip)
    archive = tmp_path / "a.zip"
    archive.write_text("")

    with patch("src.services.accounts.tg.input_account.process_single_archive", new_callable=AsyncMock) as mock_proc:
        mock_proc.return_value = ArchiveProcessingResult(valid=True, archive_path=str(archive), dir_path=str(tmp_path), user=None)
        result = await process_archives_batch(str(tmp_path))
        assert result.total == 1
        assert len(result.items) == 1


@pytest.mark.asyncio
async def test_process_dirs_batch_no_dirs(tmp_path):
    from src.services.accounts.tg.input_account import process_dirs_batch

    test_dir = (tmp_path / "fake_dir")
    test_dir.mkdir(parents=True)

    with pytest.raises(DirNotFount):
        await process_dirs_batch(str(test_dir))


@pytest.mark.asyncio
async def test_process_dirs_batch_calls_process_single_dir(tmp_path):
    from src.services.accounts.tg.input_account import process_dirs_batch

    test_dir = tmp_path / "test_processing_dir"
    (test_dir / "dir1").mkdir(parents=True)

    with patch("src.services.accounts.tg.input_account.process_single_dir", new_callable=AsyncMock) as mock_proc:
        mock_proc.return_value = BaseAccountProcessingResult(valid=True, dir_path=str(tmp_path / "dir1"), user=None)

        result = await process_dirs_batch(str(test_dir))

        assert result.total == 1
        assert len(result.items) == 1


@pytest.mark.asyncio
async def test_process_single_dir_valid(tmp_path):
    from src.services.accounts.tg.input_account import process_single_dir
    (tmp_path / "acc").mkdir()
    user = SimpleNamespace(id=1, phone="123")
    with patch("src.services.accounts.tg.input_account.check_valid_accounts_telethon", return_value=user):
        result = await process_single_dir(str(tmp_path / "acc"))
        assert result.valid
        assert result.user.id == 1


@pytest.mark.asyncio
async def test_process_single_dir_invalid(tmp_path):
    from src.services.accounts.tg.input_account import process_single_dir
    (tmp_path / "acc").mkdir()
    with patch("src.services.accounts.tg.input_account.check_valid_accounts_telethon", return_value=None):
        result = await process_single_dir(str(tmp_path / "acc"))
        assert not result.valid



@pytest.mark.asyncio
async def test_process_single_archive_valid(tmp_path):
    from src.services.accounts.tg.input_account import process_single_archive
    archive = tmp_path / "a.zip"
    archive.write_text("")
    user = SimpleNamespace(id=1, phone="123")

    with patch("src.services.accounts.tg.input_account.extract_archive_to_temp", return_value=str(tmp_path)), \
         patch("src.services.accounts.tg.input_account.check_valid_accounts_telethon", return_value=user):
        result = await process_single_archive(str(archive))
        assert result.valid
        assert result.user.id == 1

@pytest.mark.asyncio
async def test_process_single_archive_invalid(tmp_path):
    from src.services.accounts.tg.input_account import process_single_archive
    archive = tmp_path / "a.zip"
    archive.write_text("")

    with patch("src.services.accounts.tg.input_account.extract_archive_to_temp", return_value=str(tmp_path)), \
         patch("src.services.accounts.tg.input_account.check_valid_accounts_telethon", return_value=None):
        result = await process_single_archive(str(archive))
        assert not result.valid