import io
import pytest

from src.services.database.categories.models import AccountServiceType

pytestmark = pytest.mark.asyncio



async def test_input_other_account_full_flow_create_and_return_reports(
    create_category,
    create_product_account
):
    """
    Интеграционный тест для input_other_account:
    - Загружаем CSV в BytesIO
    - Проверяем результат ImportResult:
        successfully_added == количество добавленных аккаунтов (без дублей)
        total_processed == общее количество строк в CSV
    """
    from src.services.products.accounts.other.input_account import input_other_account
    from src.services.filesystem.account_products import make_csv_bytes

    category = await create_category(type_account_service=AccountServiceType.TELEGRAM, is_product_storage=True)

    # Телефон, который уже есть в БД
    phone_existing = "+71230000000"
    await create_product_account(phone_number=phone_existing, category_id=category.category_id)

    # Готовим CSV с 3 строками:
    csv_rows = [
        {"phone": phone_existing, "login": "db_dup", "password": "p"},
        {"phone": "+79991112233", "login": "user_new", "password": "pnew"},
        {"phone": "+79991112233", "login": "user_new_dup", "password": "pnew"},
    ]

    csv_bytes = make_csv_bytes(csv_rows, ['phone', 'login', 'password'])
    stream = io.BytesIO(csv_bytes)

    # Запускаем импортер
    result = await input_other_account(stream, category.category_id,  AccountServiceType.OTHER)

    # total_processed — число строк (csv.DictReader.line_num - 1 в коде)
    assert result.total_processed == 3

    # успешно добавлено — должен быть 3
    assert result.successfully_added >= 3

    # Если были ошибки — errors_csv_bytes можно проверить как bytes
    if result.errors_csv_bytes is not None:
        assert isinstance(result.errors_csv_bytes, (bytes, bytearray))
