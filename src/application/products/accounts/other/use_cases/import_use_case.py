import io
from logging import Logger
from typing import List

from src.application.crypto.crypto_context import CryptoProvider
from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.products.accounts import AccountProductService, AccountStorageService
from src.application.products.accounts.other.dto import ImportResult, REQUIRED_HEADERS, AccountImportData
from src.database.models.categories import AccountServiceType
from src.domain.crypto.encrypt import make_account_key
from src.domain.crypto.key_ops import encrypt_text
from src.exceptions import InvalidFormatRows, CategoryNotFound, TheCategoryNotStorageAccount
from src.infrastructure.files.csv_parse import parse_csv_from_bytes
from src.infrastructure.files.file_system import make_csv_bytes
from src.models.create_models.accounts import CreateAccountStorageDTO, CreateProductAccountDTO


class ImportOtherAccountsUseCase:

    def __init__(
        self,
        crypto_provider: CryptoProvider,
        publish_event_handler: PublishEventHandler,
        account_product_service: AccountProductService,
        account_storage_service: AccountStorageService,
        logger: Logger,
    ):
        self.crypto_provider = crypto_provider
        self.publish_event_handler = publish_event_handler
        self.account_product_service = account_product_service
        self.account_storage_service = account_storage_service
        self.logger = logger

    async def execute(
        self,
        stream: io.BytesIO,
        category_id: int,
        type_account_service: AccountServiceType
    ) -> ImportResult:
        """
        Добавит аккаунты из csv файла. В файле должны содержаться заголовки: phone, email, password
        :param stream: Поток байт из csv файла содержащий данные для входа в аккаунт
        :except CategoryNotFound: Категория не найдена
        :except TheCategoryNotStorageAccount: Категория не хранит аккаунты
        :except TypeAccountServiceNotFound: Тип сервиса не найден
        """
        reader = parse_csv_from_bytes(stream)

        # Проверяем заголовки
        if not REQUIRED_HEADERS <= list(reader.fieldnames or []):
            raise InvalidFormatRows()

        accounts: List[AccountImportData] = []
        errors_account: List[AccountImportData] = []
        errors_csv_bytes = None
        duplicates_csv_bytes = None

        for i, row in enumerate(reader, start=1):
            account_data = AccountImportData(
                phone=(row.get("phone") or "").strip(),
                login=(row.get("login") or "").strip(),
                password=(row.get("password") or "").strip()
            )

            if (
                    not account_data.phone or
                    not account_data.login or
                    not account_data.password or
                    (len(account_data.phone) > 100)  # 100 символов в телефоне это ограничение для БД
            ):
                errors_account.append(account_data)
                continue

            accounts.append(account_data)

        successfully_added = len(accounts)
        errors_added = await self._import_in_db(
            account_data=accounts,
            type_account_service=type_account_service,
            category_id=category_id
        )
        if errors_added:
            errors_account += errors_added
            successfully_added -= len(errors_added)

        if errors_account:
            need_list = [acc.model_dump() for acc in errors_account]
            errors_csv_bytes = make_csv_bytes(need_list, REQUIRED_HEADERS)

        return ImportResult(
            successfully_added=successfully_added,
            total_processed=reader.line_num - 1,
            errors_csv_bytes=errors_csv_bytes,
            duplicates_csv_bytes=duplicates_csv_bytes
        )

    async def _import_in_db(
        self,
        account_data: List[AccountImportData],
        type_account_service: AccountServiceType,
        category_id: int
    ) -> List[AccountImportData]:
        """
        :return: Список неудачно добавленных аккаунтов
        """
        errors_added = []
        crypto = self.crypto_provider.get()

        for account in account_data:
            try:

                # персональный DEK аккаунта
                encrypted_key_b64, account_key, nonce = make_account_key(crypto.kek)

                login_encrypted, login_nonce, _ = encrypt_text(account.login, account_key)
                password_encrypted, password_nonce, _ = encrypt_text(account.password, account_key)

                acc = await self.account_storage_service.create_account_storage(
                    data=CreateAccountStorageDTO(
                        is_file=False,
                        type_account_service=type_account_service,
                        checksum="",  # это не надо для данного типа аккаунтов
                        encrypted_key=encrypted_key_b64,
                        encrypted_key_nonce=nonce,
                        phone_number=account.phone,
                        login_encrypted=login_encrypted,
                        login_nonce=login_nonce,
                        password_encrypted=password_encrypted,
                        password_nonce=password_nonce,
                    ),
                    make_commit=True,

                )
                await self.account_product_service.create_product_account(
                    data=CreateProductAccountDTO(
                        category_id=category_id,
                        account_storage_id=acc.account_storage_id
                    ),
                    make_commit=True,
                    filling_redis=True,
                )
            except CategoryNotFound:
                raise
            except TheCategoryNotStorageAccount:
                raise
            except Exception as e:
                message_log = f"#Ошибка при импорте other аккаунта в БД: {str(e)}"
                self.logger.exception(message_log)

                await self.publish_event_handler.send_log(text=message_log)

                errors_added.append(account)

        return errors_added