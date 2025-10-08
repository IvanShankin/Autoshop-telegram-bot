import os

import pytest
from orjson import orjson
from sqlalchemy import delete, select

from src.services.system.actions.actions import get_all_types_payments, add_backup_log, update_type_payment, \
    get_type_payment, update_ui_image, get_all_ui_images, get_ui_image
from src.services.system.models import Settings, BackupLogs, TypePayments
from src.services.system.actions import get_settings, update_settings
from src.services.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from src.services.system.models.models import UiImages
from tests.fixtures.helper_fixture import create_settings
from tests.fixtures.helper_functions import comparison_models



@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis',[True,False])
async def test_get_settings(use_redis, create_settings):
    if use_redis:
        async with get_redis() as session_redis:
            await session_redis.set(
                f'settings',
                orjson.dumps(create_settings.to_dict())
            )
        async with get_db() as session_db:
            await session_db.execute(delete(Settings))
    else:
        async with get_redis() as session_redis:
            await session_redis.flushdb()


    selected_settings = await get_settings()

    await comparison_models(create_settings, selected_settings, ['settings_id'])

@pytest.mark.asyncio
async def test_update_settings(create_settings):
    """Проверяем, что update_user меняет данные в БД и Redis"""
    # изменяем данные пользователя
    settings = create_settings
    settings.FAQ = "new FAQ"

    updated_settings = await update_settings(settings) # проверяемый метод

    async with get_db() as session_db:
        settings_db = (await session_db.execute(select(Settings))).scalars().first()

    await comparison_models(settings, settings_db, ['settings_id'])# проверка БД
    await comparison_models(settings, updated_settings, ['settings_id'])# проверка возвращаемого объекта

    # проверка Redis
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f"settings")
        assert redis_data is not None
        redis_settings = Settings(**orjson.loads(redis_data))
        await comparison_models(settings, redis_settings, ['settings_id'])# проверка redis

@pytest.mark.asyncio
async def test_get_ui_image_from_redis(create_ui_image, replacement_redis):
    """Проверяет, что get_ui_image возвращает объект из Redis, если он там есть"""
    ui_image, abs_path = await create_ui_image(key="profile")

    async with get_redis() as redis_session:
        await redis_session.set(
            f"ui_image:{ui_image.key}",
            orjson.dumps(ui_image.to_dict())
        )

    result = await get_ui_image(ui_image.key)
    assert result is not None
    assert result.key == ui_image.key
    assert os.path.exists(abs_path)

@pytest.mark.asyncio
async def test_get_ui_image_from_db(create_ui_image, replacement_redis):
    """Проверяет, что get_ui_image берёт из БД, если в Redis нет"""
    ui_image, abs_path = await create_ui_image(key="main_menu")

    async with get_redis() as r:
        assert await r.get(f"ui_image:{ui_image.key}") is None

    result = await get_ui_image(ui_image.key)
    assert result is not None
    assert result.file_path.endswith("ui_sections/main_menu.png")


@pytest.mark.asyncio
async def test_get_ui_image_file_not_exists(create_ui_image, replacement_redis):
    """Проверяет, что при отсутствии файла возвращает None"""
    ui_image, abs_path = await create_ui_image(key="ghost")
    abs_path.unlink()  # удаляем файл

    result = await get_ui_image(ui_image.key)
    assert result is None


@pytest.mark.asyncio
async def test_get_all_ui_images(create_ui_image):
    """Проверяет, что возвращает все записи"""
    await create_ui_image(key="main_menu")
    await create_ui_image(key="profile")

    result = await get_all_ui_images()
    assert len(result) >= 2
    assert all(isinstance(r, UiImages) for r in result)


@pytest.mark.asyncio
async def test_update_ui_image_updates_db_and_redis(create_ui_image, replacement_redis):
    """Проверяет, что update_ui_image обновляет запись и Redis"""
    ui_image, _ = await create_ui_image(key="profile", show=True)
    new_show_value = False

    result = await update_ui_image(ui_image.key, new_show_value)
    assert result is not None
    assert result.show is new_show_value

    # проверяем Redis
    async with get_redis() as r:
        redis_data = await r.get(f"ui_image:{ui_image.key}")
        assert redis_data is not None
        parsed = orjson.loads(redis_data)
        assert parsed["show"] == new_show_value

@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis',[True,False])
async def test_get_all_types_payments(create_type_payment, use_redis):
    type_payment_2 = await create_type_payment(filling_redis=use_redis, index=2)
    type_payment_0 = await create_type_payment(filling_redis=use_redis, index=0)
    type_payment_1 = await create_type_payment(filling_redis=use_redis, index=1)

    result_fun = await get_all_types_payments()

    # проверка на отсортированость
    assert type_payment_0.to_dict() == result_fun[0].to_dict()
    assert type_payment_1.to_dict() == result_fun[1].to_dict()
    assert type_payment_2.to_dict() == result_fun[2].to_dict()



@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', [True, False])
async def test_get_type_payment_returns_correct_data(create_type_payment, use_redis):
    """Проверяем, что get_type_payment возвращает корректные данные (и из Redis, и из БД)."""
    type_payment = await create_type_payment(filling_redis=use_redis)

    result = await get_type_payment(type_payment.type_payment_id)

    assert result is not None
    assert result.type_payment_id == type_payment.type_payment_id
    assert result.name_for_user == type_payment.name_for_user
    assert result.commission == type_payment.commission

    if use_redis:
        async with get_redis() as r:
            redis_value = await r.get(f"type_payments:{type_payment.type_payment_id}")
            assert redis_value is not None
            data = orjson.loads(redis_value)
            assert data["name_for_user"] == type_payment.name_for_user


@pytest.mark.asyncio
async def test_update_type_payment_simple_fields(create_type_payment):
    """Обновление простых полей (name_for_user, commission)."""
    tp = await create_type_payment(filling_redis=False)

    updated = await update_type_payment(
        tp.type_payment_id,
        name_for_user="Updated Payment",
        commission=9.5
    )

    assert updated.name_for_user == "Updated Payment"
    assert updated.commission == 9.5

    # проверим в БД
    async with get_db() as session_db:
        result = await session_db.execute(
            select(TypePayments).where(TypePayments.type_payment_id == tp.type_payment_id)
        )
        tp_db = result.scalar_one()
        assert tp_db.name_for_user == "Updated Payment"
        assert tp_db.commission == 9.5

    async with get_redis() as session_redis:
        result_redis = await session_redis.get('all_types_payments')
        types_payments = orjson.loads(result_redis)

        assert types_payments[0] == updated.to_dict()


@pytest.mark.asyncio
async def test_update_type_payment_index_shift_up(create_type_payment):
    """
    Проверяем, что при перемещении индекса вниз (new_index > old_index)
    промежуточные записи смещаются на -1.
    """
    tp0 = await create_type_payment(index=0, filling_redis=False)
    tp1 = await create_type_payment(index=1, filling_redis=False)
    tp2 = await create_type_payment(index=2, filling_redis=False)

    # Меняем tp0 с индекса 0 → на индекс 2
    updated = await update_type_payment(tp0.type_payment_id, index=2)

    async with get_db() as session_db:
        result = await session_db.execute(select(TypePayments).order_by(TypePayments.index))
        all_types = result.scalars().all()

    indexes = {tp.type_payment_id: tp.index for tp in all_types}

    # tp0 теперь на позиции 2
    assert indexes[tp0.type_payment_id] == 2
    # tp1 и tp2 сдвинулись на -1
    assert indexes[tp1.type_payment_id] == 0
    assert indexes[tp2.type_payment_id] == 1


@pytest.mark.asyncio
async def test_update_type_payment_index_shift_down(create_type_payment):
    """
    Проверяем, что при перемещении индекса вверх (new_index < old_index)
    промежуточные записи смещаются на +1.
    """
    tp0 = await create_type_payment(index=0, filling_redis=False)
    tp1 = await create_type_payment(index=1, filling_redis=False)
    tp2 = await create_type_payment(index=2, filling_redis=False)

    # Меняем tp2 с индекса 2 → на индекс 0
    updated = await update_type_payment(tp2.type_payment_id, index=0)

    async with get_db() as session_db:
        result = await session_db.execute(select(TypePayments).order_by(TypePayments.index))
        all_types = result.scalars().all()

    indexes = {tp.type_payment_id: tp.index for tp in all_types}

    # tp2 теперь на позиции 0
    assert indexes[tp2.type_payment_id] == 0
    # tp0 и tp1 сдвинулись на +1
    assert indexes[tp0.type_payment_id] == 1
    assert indexes[tp1.type_payment_id] == 2


@pytest.mark.asyncio
async def test_add_backup_log_creates_record():
    """Проверка, что add_backup_log создаёт запись в БД."""
    file_path = "/tmp/test_backup.sql"
    size_kb = 123

    new_log = await add_backup_log(file_path, size_kb)

    assert new_log.backup_log_id is not None
    assert new_log.file_path == file_path
    assert new_log.size_in_kilobytes == size_kb

    async with get_db() as session_db:
        result = await session_db.execute(
            select(BackupLogs).where(BackupLogs.backup_log_id == new_log.backup_log_id)
        )
        log_db = result.scalar_one()
        assert log_db.file_path == file_path
        assert log_db.size_in_kilobytes == size_kb
