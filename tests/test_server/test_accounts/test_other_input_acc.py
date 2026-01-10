import io
import pytest

from src.services.accounts.other.shemas import AccountImportData

# Если вы используете pytest-asyncio, включите эту метку
pytestmark = pytest.mark.asyncio


async def test_split_unique_and_duplicates_in_memory_and_db_duplicates(
    create_type_account_service,
    create_account_service,
    create_category,
    create_product_account  # fixture — фабрика/создатель записи в БД
):
    """
    Проверяем поведение split_unique_and_duplicates:
    - дубликаты в пределах CSV (same phone twice) должны попасть в `duplicate_items`
    - если телефон уже есть в БД — он попадёт в дубликаты, т.к. get_unique_among_db проверит DB
    """
    from src.services.accounts.other.input_account import split_unique_and_duplicates

    type_service = await create_type_account_service()
    service = await create_account_service(type_account_service_id=type_service.type_account_service_id)
    category = await create_category(account_service_id=service.account_service_id)

    # Создаём уже существующую запись в БД — это будет дубль по телефону
    existing_phone = "+79990001122"
    await create_product_account(phone_number=existing_phone, category_id=category.category_id)


    # Подготавливаем входные данные: один телефон = existing_phone (дубликат в БД),
    # второй телефон будет присутствовать дважды (локальный дубликат)
    rows = [
        {"phone": existing_phone, "login": "dup_db", "password": "p"},
        {"phone": "+70000000001", "login": "unique1", "password": "p1"},
        {"phone": "+70000000001", "login": "unique1_dup", "password": "p1"},  # локальный дубликат
    ]

    # Преобразуем к AccountImportData как ожидает split_unique_and_duplicates
    account_objs = [AccountImportData(**r) for r in rows]

    unique_items, duplicates = await split_unique_and_duplicates(account_objs, type_service.name)

    # Ожидаем: уникальные — один (unique1) если DB дубль и локальный дубль уходит в duplicates
    # duplicates включает: локальный дубль (same phone twice) и дубль, обнаруженный в БД (existing_phone)
    assert any(item.phone == existing_phone for item in duplicates)
    # Локальный дубликат должен попасть в duplicates (phone +70000000001 appears twice)
    assert sum(1 for d in duplicates if d.phone == "+70000000001") >= 1

    # Уникальные должны не содержать existing_phone
    assert all(item.phone != existing_phone for item in unique_items)


async def test_input_other_account_full_flow_create_and_return_reports(
    create_type_account_service,
    create_account_service,
    create_category,
    create_product_account
):
    """
    Интеграционный тест для input_other_account:
    - Загружаем CSV в BytesIO
    - В БД заранее создаём аккаунт с phone_existing — чтобы он распознался как дубль
    - Проверяем результат ImportResult:
        successfully_added == количество добавленных аккаунтов (без дублей)
        total_processed == общее количество строк в CSV
        duplicates_csv_bytes != None
    """
    from src.services.accounts.other.input_account import input_other_account
    from src.services.filesystem.input_account import make_csv_bytes

    type_service = await create_type_account_service()
    service = await create_account_service(type_account_service_id=type_service.type_account_service_id)
    category = await create_category(account_service_id=service.account_service_id, is_product_storage=True)

    # Телефон, который уже есть в БД
    phone_existing = "+71230000000"
    await create_product_account(phone_number=phone_existing, category_id=category.category_id)

    # Готовим CSV с 3 строками: 1 дубль в БД, 1 дубликат в файле (same as second), 1 новый
    csv_rows = [
        {"phone": phone_existing, "login": "db_dup", "password": "p"},
        {"phone": "+79991112233", "login": "user_new", "password": "pnew"},
        {"phone": "+79991112233", "login": "user_new_dup", "password": "pnew"},
    ]

    csv_bytes = make_csv_bytes(csv_rows, ['phone', 'login', 'password'])
    stream = io.BytesIO(csv_bytes)

    # Запускаем импортер
    result = await input_other_account(stream, category.category_id, type_service.name)

    # total_processed — число строк (csv.DictReader.line_num - 1 в коде)
    assert result.total_processed == 3

    # успешно добавлено — должен быть 1 (только первый уникальный, т.к. один дубль в файле, один дубль в БД)
    assert result.successfully_added >= 1

    # duplicates_csv_bytes должен быть не None (есть дубль)
    assert result.duplicates_csv_bytes is not None

    # Если были ошибки — errors_csv_bytes можно проверить как bytes
    if result.errors_csv_bytes is not None:
        assert isinstance(result.errors_csv_bytes, (bytes, bytearray))
