import asyncio
import os
import shutil
import tempfile
from logging import Logger
from pathlib import Path
from typing import AsyncGenerator

from src.application.products.accounts.other.dto.schemas import REQUIRED_HEADERS
from src.application.products.accounts.tg.dto.schemas import CreatedEncryptedArchive
from src.config import Config
from src.domain.crypto.encrypt import encrypt_folder, make_account_key
from src.domain.crypto.utils import sha256_file
from src.infrastructure.files._media_paths import create_path_account
from src.application.crypto.crypto_context import CryptoProvider
from src.application.events.publish_event_handler import PublishEventHandler
from src.domain.crypto.decrypt import decrypt_folder
from src.domain.crypto.key_ops import unwrap_dek
from src.domain.crypto.models import CryptoContext
from src.database.models.categories import AccountStorage, AccountServiceType, StorageStatus
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.rabbit_mq.producer import publish_event
from src.models.read_models import AccountStorageDTO, LogLevel, EventSentLog
from src.infrastructure.files.file_system import move_file, make_csv_bytes, make_archive
from src.utils.core_logger import get_logger


class AccountService:

    def __init__(
        self,
        publish_event_handler: PublishEventHandler,
        path_builder: PathBuilder,
        crypto_provider: CryptoProvider,
        logger: Logger,
    ):
        self.publish_event_handler = publish_event_handler
        self.path_builder = path_builder
        self.crypto_provider = crypto_provider
        self.logger = logger

    async def move_in_account(
        self,
        account: AccountStorage,
        type_service_name: AccountServiceType,
        status: StorageStatus
    ) -> bool:
        """
        Перенос аккаунтов к `status` удалив исходное местоположение.
        :param account: AccountStorage.
        :param type_service_name: тип сервиса аккаунта
        :param status: статус аккаунта который будет в конечном пути
        :return: Если возникнет ошибка или аккаунт не переместится, то вернёт False
        """
        orig = None
        final = None
        try:
            orig = self.path_builder.build_path_account(
                status=account.status,
                type_account_service=account.type_account_service,
                uuid=account.storage_uuid
            )
            final = self.path_builder.build_path_account(
                status=status,
                type_account_service=type_service_name,
                uuid=account.storage_uuid
            )

            moved = await move_file(orig, final)
            if not moved:
                return False

            # Удаление директории где хранится аккаунт (uui). Директория уже будет пустой
            if os.path.isdir(str(Path(orig).parent)):
                shutil.rmtree(str(Path(orig).parent))

            return True
        except Exception as e:
            text = (
                f"#Ошибка при переносе аккаунта к {status.value}. \n"
                f"Исходный путь: {orig if orig else "none"} \n"
                f"Финальный путь: {final if final else "none"} \n"
                f"account_storage_id: {account.account_storage_id if account.account_storage_id else "none"} \n"
                f"Ошибка: {str(e)}"
            )
            self.logger.exception(text)

            await self.publish_event_handler.send_log(text=text, log_lvl=LogLevel.ERROR)

            return False

    async def encrypted_tg_account(
        self,
        src_directory: str,
        dest_encrypted_path: str
    ) -> CreatedEncryptedArchive:
        """
        Шифрует данные TG аккаунта в указанный путь.
        Ключ генерируется здесь, путь НЕ генерируется.
        """

        try:
            crypto = self.crypto_provider.get()
            encrypted_key_b64, account_key, nonce = make_account_key(crypto.kek)

            # создаём директорию под файл
            Path(dest_encrypted_path).parent.mkdir(parents=True, exist_ok=True)

            # шифруем
            encrypt_folder(
                folder_path=src_directory,
                encrypted_path=dest_encrypted_path,
                dek=account_key
            )

            # считаем checksum
            checksum = sha256_file(dest_encrypted_path)

            return CreatedEncryptedArchive(
                result=True,
                encrypted_key_b64=encrypted_key_b64,
                path_encrypted_acc=dest_encrypted_path,
                encrypted_key_nonce=nonce,
                checksum=checksum
            )

        except Exception as e:
            logger = get_logger(__name__)
            logger.exception(f"Ошибка при шифровании: {e}")
            return CreatedEncryptedArchive(result=False)

    def decryption_tg_account(
        self,
        account_storage: AccountStorage | AccountStorageDTO,
        crypto: CryptoContext,
        status: StorageStatus,
    ):
        """
        Расшифровывает файлы Telegram-аккаунта во временную директорию.
        :param status: Статус аккаунта где в данный момент хранятся данные для него. Будет формировать путь используя этот статус.
        """

        # Расшифровываем DEK (account_key)
        account_key = unwrap_dek(
            encrypted_data_b64=account_storage.encrypted_key,
            nonce_b64=account_storage.encrypted_key_nonce,
            kek=crypto.kek
        )

        abs_path = self.path_builder.build_path_account(
            status=status,
            type_account_service=account_storage.type_account_service,
            uuid=account_storage.storage_uuid
        )

        folder_path = decrypt_folder(abs_path, account_key)  # Расшифровываем архив DEK-ом

        return folder_path

    async def get_tdata_tg_acc(self, account_storage: AccountStorage) -> AsyncGenerator[str | bool, None]:
        """
        Расшифрует папку с тг аккаунтом и создаст архив(zip) с tdata, после второго вызова удалит все созданные временные файлы
        :return: путь к архиву
        """
        crypto = self.crypto_provider.get()
        folder_path = None

        try:
            folder_path = decryption_tg_account(account_storage, crypto, account_storage.status)
            dir_for_tdata = Path(folder_path) / f'{account_storage.account_storage_id}_tdata'
            dir_for_tdata.mkdir(exist_ok=True)
            result = await move_file(str(Path(folder_path) / 'tdata'), str(dir_for_tdata))

            if not result:
                yield False
            else:

                archive_path = shutil.make_archive(
                    base_name=str(Path(folder_path) / f'{account_storage.account_storage_id}_tdata'),
                    format="zip",
                    root_dir=str(dir_for_tdata)  # должна быть директория с tdata
                )
                yield archive_path
        except Exception as e:
            self.logger.exception("#Ошибка при получении tdata с аккаунта %s: %s",
                             getattr(account_storage, "account_storage_id", None), e)
            yield False
        finally:
            if folder_path:
                await asyncio.to_thread(shutil.rmtree, folder_path, ignore_errors=True)

    async def get_session_tg_acc(self, account_storage: AccountStorage) -> AsyncGenerator[str | bool, None]:
        """
        Расшифрует папку с тг аккаунтом и вернёт путь к файлу .session, после второго вызова удалит все созданные временные файлы
        :return: Путь к файлу
        """
        crypto = self.crypto_provider.get()
        folder_path = None

        try:
            folder_path = decryption_tg_account(account_storage, crypto, account_storage.status)
            session_path = str(Path(folder_path) / 'session.session')
            if os.path.isfile(session_path):
                yield session_path
            else:
                self.logger.warning(
                    "Не_найден_файл при получении session с аккаунта %s: %s",
                    getattr(account_storage, "account_storage_id", None),
                    f"Путь поиска: {session_path}"
                )
                yield False
        except Exception as e:
            self.logger.exception("#Ошибка при получении session с аккаунта %s: %s",
                             getattr(account_storage, "account_storage_id", None), e)
            yield False
        finally:
            if folder_path:
                await asyncio.to_thread(shutil.rmtree, folder_path, ignore_errors=True)


class GenerateExample:

    def __init__(
        self,
        conf: Config
    ):
        self.conf = conf
        self.TXT_FILES = [
            "example_input_data_1.txt",
            "example_input_data_2.txt",
        ]


    def generate_example_import_other_acc(self,) -> None:
        """Создаёт пример CSV-файла для импорта аккаунтов"""

        data = [
            {
                "phone": "+79161234567",
                "login": "ivan.petrov",
                "password": "Qwerty123!",
            },
            {
                "phone": "+79169876543",
                "login": "anna.smirnova",
                "password": "StrongPass#9",
            },
            {
                "phone": "+79005554433",
                "login": "test.user",
                "password": "Test1234",
            },
        ]

        bytes_csv = make_csv_bytes(
            data=data,
            headers=REQUIRED_HEADERS,
            excel_compatible=True,
        )

        path = Path(self.conf.file_keys.example_csv_for_import_other_acc_key.path)

        path.write_bytes(bytes_csv)

    async def generate_example_import_tg_acc(self, ) -> bool:
        """
        Создаёт пример ZIP-архива для импорта аккаунтов
        Создаёт архив со структурой:
        ├── archive_1.zip
        ├── archive_2.zip
        └── dir/
            └── tdata/
                ├── example_input_data_1.txt
                └── example_input_data_2.txt
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            #  archive_1
            archive_1_dir = tmp_path / "archive_1" / "tdata"
            archive_1_dir.mkdir(parents=True)

            for name in self.TXT_FILES:
                (archive_1_dir / name).touch()

            archive_1_zip = tmp_path / "archive_1.zip"
            ok = await make_archive(
                data_for_archiving=str(tmp_path / "archive_1"),
                new_path_archive=str(archive_1_zip),
            )
            if not ok:
                return False

            #  archive_2
            archive_2_dir = tmp_path / "archive_2" / "tdata"
            archive_2_dir.mkdir(parents=True)

            for name in self.TXT_FILES:
                (archive_2_dir / name).touch()

            archive_2_zip = tmp_path / "archive_2.zip"
            ok = await make_archive(
                data_for_archiving=str(tmp_path / "archive_2"),
                new_path_archive=str(archive_2_zip),
            )
            if not ok:
                return False

            #  dir (НЕ архивируется отдельно)
            dir_tdata = tmp_path / "dir" / "tdata"
            dir_tdata.mkdir(parents=True)

            for name in self.TXT_FILES:
                (dir_tdata / name).touch()

            #  финальный архив
            ok = await make_archive(
                data_for_archiving=[
                    str(archive_1_zip),
                    str(archive_2_zip),
                    str(tmp_path / "dir"),
                ],
                new_path_archive=self.conf.file_keys.example_zip_for_import_tg_acc_key.path,
            )
            return ok


# ВСЁ ЧТО НИЖЕ УБРАТЬ ПРИ ПОЛНОМ ПЕРЕХОДЕ НА НОВУЮ ВРХИТЕКТУРУ

async def move_in_account(account: AccountStorage, type_service_name: AccountServiceType, status: StorageStatus) -> bool:
    """
    Перенос аккаунтов к `status` удалив исходное местоположение.
    :param account: AccountStorage.
    :param type_service_name: тип сервиса аккаунта
    :param status: статус аккаунта который будет в конечном пути
    :return: Если возникнет ошибка или аккаунт не переместится, то вернёт False
    """
    orig = None
    final = None
    try:
        orig = create_path_account(
            status=account.status,
            type_account_service=account.type_account_service,
            uuid=account.storage_uuid
        )
        final = create_path_account(
            status=status,
            type_account_service=type_service_name,
            uuid=account.storage_uuid
        )

        moved = await move_file(orig, final)
        if not moved:
            return False

        # Удаление директории где хранится аккаунт (uui). Директория уже будет пустой
        if os.path.isdir(str(Path(orig).parent)):
            shutil.rmtree(str(Path(orig).parent))

        return True
    except Exception as e:
        text = (
            f"#Ошибка при переносе аккаунта к {status.value}. \n"
            f"Исходный путь: {orig if orig else "none"} \n"
            f"Финальный путь: {final if final else "none"} \n"
            f"account_storage_id: {account.account_storage_id if account.account_storage_id else "none"} \n"
            f"Ошибка: {str(e)}"
        )
        logger = get_logger(__name__)
        logger.exception(text)

        event = EventSentLog(text=text)
        await publish_event(event.model_dump(), "message.send_log")

        return False



def decryption_tg_account(
    account_storage: AccountStorage | AccountStorageDTO,
    crypto: CryptoContext,
    status: StorageStatus,
):
    """
    Расшифровывает файлы Telegram-аккаунта во временную директорию.
    :param status: Статус аккаунта где в данный момент хранятся данные для него. Будет формировать путь используя этот статус.
    """

    # Расшифровываем DEK (account_key)
    account_key = unwrap_dek(
        encrypted_data_b64=account_storage.encrypted_key,
        nonce_b64=account_storage.encrypted_key_nonce,
        kek=crypto.kek
    )

    abs_path = create_path_account(
        status=status,
        type_account_service=account_storage.type_account_service,
        uuid=account_storage.storage_uuid
    )

    folder_path = decrypt_folder(abs_path, account_key) # Расшифровываем архив DEK-ом

    return folder_path



