import os

import pytest
from orjson import orjson
from sqlalchemy import delete, select

from src.services.database.system.actions.actions import get_all_types_payments, add_backup_log, update_type_payment, \
    get_type_payment, update_ui_image, get_all_ui_images, get_ui_image, get_statistics
from src.services.database.system.models import Settings, BackupLogs, TypePayments
from src.services.database.system.actions import get_settings, update_settings
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis
from src.services.database.system.models import UiImages

from tests.helpers.helper_functions import comparison_models

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

    updated_settings = await update_settings(faq=settings.FAQ) # проверяемый метод

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
async def test_create_ui_image_new_record(tmp_path, monkeypatch):
    """Проверяет, что функция создаёт новую запись и файл, если key не существует."""
    from src.services.database.system.actions import create_ui_image
    from src.utils.ui_images_data import get_config

    conf = get_config()

    # Подготовка
    fake_key = "banner"
    fake_data = b"test_image_bytes"
    fake_path = conf.paths.ui_sections_dir / (fake_key + '.png')

    # Действие
    result = await create_ui_image(fake_key, fake_data)

    # Проверки
    assert fake_path.exists(), "Файл должен быть создан"
    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages).where(UiImages.key == fake_key))
        ui_image: UiImages = result_db.scalar_one_or_none()
        assert ui_image.file_path == str(fake_path)

    async with get_redis() as session_redis:
        data_redis = await session_redis.get(f"ui_image:{fake_key}")
        ui_image_redis = orjson.loads(data_redis)

    await comparison_models(ui_image.to_dict(), ui_image_redis)


@pytest.mark.asyncio
async def test_create_ui_image_existing_record(replacement_needed_modules, monkeypatch, tmp_path, create_ui_image):
    """Проверяет, что при существующей записи файл перезаписывается и запись обновляется."""
    from src.services.database.system.actions import create_ui_image as testing_fun

    fake_data = b"new_bytes"
    origin_ui_image, abs_path = await create_ui_image(key="existing_banner")

    # Действие
    result = await testing_fun(origin_ui_image.key, fake_data)

    # Проверки
    assert os.path.isfile(origin_ui_image.file_path), "Файл должен быть перезаписан"

    async with get_db() as session_db:
        result_db = await session_db.execute(select(UiImages).where(UiImages.key == origin_ui_image.key))
        ui_image: UiImages = result_db.scalar_one_or_none()
        assert ui_image.file_path == str(abs_path)

    async with get_redis() as session_redis:
        data_redis = await session_redis.get(f"ui_image:{origin_ui_image.key}")
        ui_image_redis = orjson.loads(data_redis)

    await comparison_models(ui_image.to_dict(), ui_image_redis)


@pytest.mark.asyncio
async def test_get_ui_image_from_redis(create_ui_image):
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
async def test_get_ui_image_from_db(create_ui_image):
    """Проверяет, что get_ui_image берёт из БД, если в Redis нет"""
    ui_image, abs_path = await create_ui_image(key="main_menu")

    async with get_redis() as r:
        assert await r.get(f"ui_image:{ui_image.key}") is None

    result = await get_ui_image(ui_image.key)
    assert result is not None
    assert result.file_path.endswith(str(abs_path))


@pytest.mark.asyncio
async def test_get_all_ui_images(create_ui_image):
    """Проверяет, что возвращает все записи"""
    await create_ui_image(key="main_menu")
    await create_ui_image(key="profile")

    result = await get_all_ui_images()
    assert len(result) >= 2
    assert all(isinstance(r, UiImages) for r in result)


@pytest.mark.asyncio
async def test_update_ui_image_updates_db_and_redis(create_ui_image):
    """Проверяет, что update_ui_image обновляет запись и Redis"""
    ui_image, _ = await create_ui_image(key="profile", show=True)
    new_show_value = False

    result = await update_ui_image(ui_image.key, new_show_value, ui_image.file_id)
    assert result is not None
    assert result.show is new_show_value

    # проверяем Redis
    async with get_redis() as r:
        redis_data = await r.get(f"ui_image:{ui_image.key}")
        assert redis_data is not None
        parsed = orjson.loads(redis_data)
        assert parsed["show"] == new_show_value


@pytest.mark.asyncio
async def test_delete_ui_image(create_ui_image):
    from src.services.database.system.actions import delete_ui_image

    ui_image, _ = await create_ui_image(key="test_ui_image")
    assert os.path.isfile(ui_image.file_path) # что бы убедиться что файл был

    await delete_ui_image(ui_image.key)

    async with get_db() as session_db:
        result = await session_db.execute(select(UiImages).where(UiImages.key == ui_image.key))
        ui_image_db = result.scalar_one_or_none()

        assert not ui_image_db

    async with get_redis() as r:
        redis_data = await r.get(f"ui_image:{ui_image.key}")
        assert redis_data is None

    assert not os.path.isfile(ui_image.file_path)



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
    storage_file_name = "test_backup"
    size_bytes = 123

    new_log = await add_backup_log(
        storage_file_name,
        "storage_encrypted_dek_name",
        "encrypted_dek_b64",
        "dek_nonce_b64",
        size_bytes
    )

    assert new_log.backup_log_id is not None
    assert new_log.storage_file_name == storage_file_name
    assert new_log.size_bytes == size_bytes

    async with get_db() as session_db:
        result = await session_db.execute(
            select(BackupLogs).where(BackupLogs.backup_log_id == new_log.backup_log_id)
        )
        log_db = result.scalar_one()
        assert log_db.storage_file_name == storage_file_name
        assert log_db.size_bytes == size_bytes



@pytest.mark.asyncio
async def test_get_statistics(create_new_user, create_replenishment, create_product_account, create_purchase_account):
    users = [await create_new_user() for _ in range(3)]
    replenishments = [await create_replenishment(user_id=users[0].user_id) for _ in range(3)]
    purchase_account = [await create_purchase_account(user_id=users[0].user_id) for _ in range(3)]

    product_accounts = []
    for _ in range(3):
        _, prod_acc = await create_product_account(price=100)
        product_accounts.append(prod_acc)


    result = await get_statistics(10)


    assert result.total_users == len(users)
    assert result.new_users == len(users)
    assert result.active_users == len(users)

    assert result.quantity_sale_accounts == len(purchase_account)
    assert result.amount_sale_accounts == sum(s.purchase_price for s in purchase_account)
    assert result.total_net_profit == sum(s.net_profit for s in purchase_account)

    assert result.quantity_replenishments == 3
    assert result.amount_replenishments == sum(r.amount for r in replenishments)

    # Проверяем разбивку по платёжным системам
    assert isinstance(result.replenishment_payment_systems, list)

    total_from_payment_systems = sum(
        ps.amount_replenishments
        for ps in result.replenishment_payment_systems
    )
    assert total_from_payment_systems == result.amount_replenishments

    total_quantity_from_payment_systems = sum(
        ps.quantity_replenishments
        for ps in result.replenishment_payment_systems
    )
    assert total_quantity_from_payment_systems == result.quantity_replenishments

    assert result.funds_in_bot == 300

    assert result.accounts_for_sale == len(product_accounts)

    assert result.last_backup == "—"

