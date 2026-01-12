import csv
import io
from typing import List, Tuple

from src.bot_actions.messages import send_log
from src.exceptions import InvalidFormatRows, CategoryNotFound, TheCategoryNotStorageAccount
from src.services.accounts.other.shemas import AccountImportData, ImportResult, REQUIRED_HEADERS
from src.services.accounts.utils.helper_imports import get_unique_among_db
from src.services.database.categories.actions import add_account_storage, add_product_account
from src.services.filesystem.input_account import make_csv_bytes
from src.utils.core_logger import get_logger
from src.services.secrets import encrypt_text, make_account_key, get_crypto_context


async def input_other_account(stream: io.BytesIO, category_id: int, type_account_service: str) -> ImportResult:
    """
    Добавит аккаунты из csv файла. В файле должны содержаться заголовки: phone, email, password
    :param stream: Поток байт из csv файла содержащий данные для входа в аккаунт
    :except CategoryNotFound: Категория не найдена
    :except TheCategoryNotStorageAccount: Категория не хранит аккаунты
    :except TypeAccountServiceNotFound: Тип сервиса не найден
    """
    text = stream.read().decode("utf-8").lstrip("\ufeff")
    dialect = csv.Sniffer().sniff(text)
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    # Проверяем заголовки
    if not REQUIRED_HEADERS <= list(reader.fieldnames or []):
        raise InvalidFormatRows()


    accounts: List[AccountImportData] = []
    errors_account: List[AccountImportData] = []
    errors_csv_bytes = None
    duplicates_csv_bytes = None

    for i, row in enumerate(reader, start=1):
        print(row)
        account_data = AccountImportData(
            phone=(row.get("phone") or "").strip(),
            login = (row.get("login") or "").strip(),
            password = (row.get("password") or "").strip()
        )

        # 100 символов в телефоне это ограничение для БД
        if (
            not account_data.phone or
            not account_data.login or
            not account_data.password or
            (len(account_data.phone) > 100)
        ):
            errors_account.append(account_data)
            continue

        accounts.append(account_data)

    accounts, duplicates = await split_unique_and_duplicates(accounts, type_account_service)

    errors_added = await import_in_db(
        account_data=accounts,
        type_account_service=type_account_service,
        category_id=category_id
    )
    if errors_added:
        errors_account += errors_added
        accounts -= errors_added


    if errors_account:
        need_list = [acc.model_dump() for acc in errors_account]
        errors_csv_bytes = make_csv_bytes(need_list, REQUIRED_HEADERS)

    if duplicates:
        need_list = [acc.model_dump() for acc in duplicates]
        duplicates_csv_bytes = make_csv_bytes(need_list, REQUIRED_HEADERS)


    return ImportResult(
        successfully_added=len(accounts),
        total_processed=reader.line_num - 1,
        errors_csv_bytes=errors_csv_bytes,
        duplicates_csv_bytes=duplicates_csv_bytes
    )


async def split_unique_and_duplicates(
    account_data: List[AccountImportData],
    type_account_service: str
) -> Tuple[List[AccountImportData], List[AccountImportData]]:
    """
    :return: Tuple[Уникальные, Дубликаты]
    """
    unique_items = []
    duplicate_items = []

    seen_phones = set()

    for account in account_data:
        if account.phone in seen_phones:
            duplicate_items.append(account)

        seen_phones.add(account.phone)
        unique_items.append(account)

    # отбор уникальных среди БД
    unique_items, duplicate_2 = await get_unique_among_db(unique_items, type_account_service)
    return unique_items, duplicate_items + duplicate_2


async def import_in_db(
    account_data: List[AccountImportData],
    type_account_service: str,
    category_id: int
) ->  List[AccountImportData]:
    """
    :return: Список неудачно добавленных аккаунтов
    """
    errors_added = []
    crypto = get_crypto_context()

    for account in account_data:
        try:

            # персональный DEK аккаунта
            encrypted_key_b64, account_key, nonce = make_account_key(crypto.kek)

            login_encrypted, login_nonce, _  = encrypt_text(account.login, account_key)
            password_encrypted, password_nonce, _  = encrypt_text(account.password, account_key)

            acc = await add_account_storage(
                type_service_name=type_account_service,
                checksum="",  # это не надо для данного типа аккаунтов
                encrypted_key=encrypted_key_b64,
                encrypted_key_nonce=nonce,
                phone_number=account.phone,
                login_encrypted=login_encrypted,
                login_nonce=login_nonce,
                password_encrypted=password_encrypted,
                password_nonce=password_nonce,
            )
            await add_product_account(
                category_id=category_id,
                account_storage_id=acc.account_storage_id
            )
        except CategoryNotFound:
            raise
        except TheCategoryNotStorageAccount:
            raise
        except Exception as e:
            message_log = f"#Ошибка при добавлении other аккаунта в БД: {str(e)}"
            logger = get_logger(__name__)
            logger.exception(message_log)
            await send_log(message_log)
            errors_added.append(account)

    return errors_added
