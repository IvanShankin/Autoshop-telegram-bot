import asyncio
import shutil
import tempfile
from logging import Logger
from pathlib import Path
from typing import AsyncGenerator, Any, List, Tuple

from src.application.models.products.accounts import AccountStorageService, AccountProductService
from src.application.products.accounts.account_service import AccountService
from src.application.products.accounts.tg.dto.schemas import ImportResult, BaseAccountProcessingResult, \
    ArchivesBatchResult, ArchiveProcessingResult, DirsBatchResult
from src.database.models.categories import AccountServiceType
from src.exceptions import ArchiveNotFount, DirNotFount
from src.infrastructure.files.file_system import extract_archive_to_temp, archive_if_not_empty, cleanup_used_data, \
    make_archive
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.telegram.account_client import TelegramAccountClient
from src.models.create_models.accounts import CreateAccountStorageDTO, CreateProductAccountDTO
from src.models.update_models import UpdateAccountStorageDTO
from src.utils.pars_number import phone_in_e164

# ограничиваем число параллельных обработок
SEM = asyncio.Semaphore(7)

class ImportTelegramAccountsUseCase:

    def __init__(
        self,
        account_storage_service: AccountStorageService,
        account_service: AccountService,
        account_product_service: AccountProductService,
        path_builder: PathBuilder,
        tg_client: TelegramAccountClient,
        logger: Logger,
    ):
        self.account_storage_service = account_storage_service
        self.account_service = account_service
        self.account_product_service = account_product_service
        self.path_builder = path_builder
        self.tg_client = tg_client
        self.logger = logger

    async def import_telegram_accounts_from_archive(
        self,
        archive_path: str,
        category_id: int,
        type_account_service: AccountServiceType
    ) -> AsyncGenerator[ImportResult | None, Any]:
        """
        При первом вызове интегрирует аккаунты в бота,
        при втором удалит все созданные временные файлы, так же и архивы с невалидными/дублирующими аккаунтами
        """
        archive_path_del = Path(archive_path)
        dir_with_archive = archive_path_del.parent  # временная директория

        if not archive_path.lower().endswith(".zip"):
            shutil.rmtree(dir_with_archive, ignore_errors=True)
            archive_path_del.unlink(missing_ok=True)
            raise ArchiveNotFount()

        base_dir = await extract_archive_to_temp(archive_path)

        invalid_dir = tempfile.mkdtemp()
        duplicate_dir = tempfile.mkdtemp()

        try:
            archives_result = await self._process_archives_batch(base_dir)
        except ArchiveNotFount:
            archives_result = None

        try:
            dirs_result = await self._process_dirs_batch(base_dir)
        except DirNotFount:
            dirs_result = None

        # собираем все результаты вместе
        all_items = []
        if archives_result:
            all_items.extend(archives_result.items)
        if dirs_result:
            all_items.extend(dirs_result.items)

        unique_items, duplicate_items, invalid_items = await self._split_unique_and_duplicates(
            all_items, type_account_service
        )

        # Архивируем повторяющиеся аккаунты
        await self._process_inappropriate_acc(duplicate_items, duplicate_dir)
        await self._process_inappropriate_acc(invalid_items, invalid_dir)

        # Грузим уникальные в БД
        successfully_added = await self._import_in_db(unique_items, type_account_service, invalid_dir, category_id)

        invalid_archive = await archive_if_not_empty(invalid_dir)
        duplicate_archive = await archive_if_not_empty(duplicate_dir)

        result = ImportResult(
            successfully_added=successfully_added,
            total_processed=len(all_items),
            invalid_archive_path=invalid_archive,
            duplicate_archive_path=duplicate_archive,
        )

        # отдаём результат пользователю
        yield result

        # затем асинхронно чистим всё в thread (без блокирования loop)
        await cleanup_used_data(
            dir_with_archive=str(dir_with_archive),
            archive_path=archive_path,
            base_dir=base_dir,
            invalid_dir=invalid_dir,
            duplicate_dir=duplicate_dir,
            invalid_archive=invalid_archive,
            duplicate_archive=duplicate_archive,
            all_items=all_items,
        )

        yield None

    async def _import_in_db(
        self,
        all_items: List[BaseAccountProcessingResult],
        type_account_service: AccountServiceType,
        invalid_dir: str,
        category_id: int
    ) -> int:
        """
        Импортирует аккаунты в БД
        :param all_items: все уникальные данные об аккаунтах
        :param type_account_service: тип сервиса куда добавляем
        :param invalid_dir: путь к директории с невалидными аккаунтами
        :param category_id: категория куда необходимо добавить
        :return: успешное количество добавленных аккаунтов
        """
        successfully_added = 0
        for item in all_items:
            if not item.valid:
                continue

            user = item.user
            phone = user.phone

            #  создаём запись в БД
            acc = await self.account_storage_service.create_account_storage(
                data=CreateAccountStorageDTO(
                    is_file=True,
                    type_account_service=type_account_service,
                    checksum="",  # пока пусто
                    encrypted_key="",  # пока пусто
                    encrypted_key_nonce="",  # пока пусто
                    phone_number=phone,
                    tg_id=user.id
                ),
                make_commit=True,
            )

            # Полный путь к будущему зашифрованному файлу
            dest_path = self.path_builder.build_path_account(acc.status, type_account_service, acc.storage_uuid)

            #  шифруем
            enc = await self.account_service.encrypted_tg_account(
                src_directory=item.dir_path,
                dest_encrypted_path=str(dest_path)
            )

            if not enc.result:
                # Архив битый → перемещаем в invalid
                dst = Path(invalid_dir) / Path(item.dir_path).name
                shutil.copytree(item.dir_path, dst)  # копируем к невалидным
                await make_archive(str(dst), str(dst.with_suffix(".zip")))
                continue

            # обновляем запись в БД после успешного шифрования
            acc = await self.account_storage_service.update_account_storage(
                account_storage_id=acc.account_storage_id,
                data=UpdateAccountStorageDTO(
                    checksum=enc.checksum,
                    encrypted_key=enc.encrypted_key_b64,
                    encrypted_key_nonce=enc.encrypted_key_nonce,
                ),
                make_commit=True,
                filling_redis=True,
            )

            await self.account_product_service.create_product_account(
                data=CreateProductAccountDTO(
                    category_id=category_id,
                    account_storage_id=acc.account_storage_id,
                ),
                make_commit=True,
                filling_redis=True,
            )
            successfully_added += 1

        return successfully_added

    async def _split_unique_and_duplicates(
        self,
        items: List[BaseAccountProcessingResult],
        type_account_service: AccountServiceType
    ) -> Tuple[List[BaseAccountProcessingResult], List[BaseAccountProcessingResult], List[BaseAccountProcessingResult]]:
        """
        Отберёт уникальные аккаунты
        :return: Tuple[Уникальные аккаунты, Дубликаты, Невалидные аккаунты]
        """
        unique_items: List[BaseAccountProcessingResult] = []
        duplicate_items = []
        invalid_item = []

        seen_ids = set()
        seen_phones = set()

        for item in items:
            if not item.valid or not item.user:
                invalid_item.append(item)
                continue

            user = item.user
            tg_id = user.id
            phone = user.phone.strip() if user.phone else None

            duplicate = (
                    tg_id in seen_ids or
                    (phone and phone in seen_phones)
            )

            if duplicate:
                self.logger.info(f"[split_unique_and_duplicates] - Найден дубликат аккаунта: {item.dir_path}")
                duplicate_items.append(item)
                continue

            seen_ids.add(tg_id)
            if phone:
                seen_phones.add(phone)

            unique_items.append(item)

        unique_items, duplicate_items_2 = await self._get_unique_tg_acc_among_db(unique_items, type_account_service)

        return unique_items, duplicate_items + duplicate_items_2, invalid_item

    async def _get_unique_tg_acc_among_db(
        self,
        account_data: List[BaseAccountProcessingResult],
        type_account_service: AccountServiceType
    ) -> Tuple[List[BaseAccountProcessingResult], List[BaseAccountProcessingResult]]:
        """
        Отберёт уникальные аккаунты среди БД.
        :param type_account_service: Тип сервиса ("telegram" и т.д.)
        :return: Tuple[Уникальные, Дубликаты]
        """
        unique_items = []
        duplicate_items = []

        numbers_in_db = await self.account_storage_service.get_all_phone_numbers_by_service(type_account_service)
        tg_id_in_db = await self.account_storage_service.get_all_tg_ids()

        for acc_data in account_data:
            # преобразовываем номер т.к. такой формат хранится в БД
            if phone_in_e164(acc_data.phone) in numbers_in_db:
                self.logger.info(
                    f"[get_unique_tg_acc_among_db] - Найден дублик аккаунта по номеру телефона: {acc_data.phone}"
                )
                duplicate_items.append(acc_data)
                continue

            if acc_data.user.id in tg_id_in_db:
                self.logger.info(f"[get_unique_tg_acc_among_db] - Найден дублик аккаунта по tg_id: {acc_data.user.id}")
                duplicate_items.append(acc_data)
                continue

            unique_items.append(acc_data)

        return unique_items, duplicate_items

    async def _process_inappropriate_acc(self, inappropriate_items, archive_dir):
        """Архивирует неподходящие аккаунты (дубликаты/невалидные)"""
        for item in inappropriate_items:
            try:
                # создаём папку для конкретного аккаунта
                dst = Path(archive_dir) / Path(item.dir_path).name

                # копируем к себе
                shutil.copytree(item.dir_path, dst)

                # теперь архивируем ЭТУ копию
                await make_archive(str(dst), str(dst.with_suffix(".zip")))

                shutil.rmtree(dst)
            except Exception as e:
                self.logger.exception("Ошибка при архивировании неподходящего аккаунта", exc_info=e)

    async def _process_archives_batch(self, directory: str) -> ArchivesBatchResult:
        archives = [str(p) for p in Path(directory).glob("*.zip")]
        if not archives:
            raise ArchiveNotFount()

        self.logger.info(f"Найдено архивов: {len(archives)}")

        tasks = [asyncio.create_task(self._process_single_archive(path)) for path in archives]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        fixed: List[ArchiveProcessingResult] = []
        for r in results:
            if isinstance(r, Exception):
                self.logger.exception("Ошибка при обработке архива", exc_info=r)
            else:
                fixed.append(r)

        return ArchivesBatchResult(items=fixed, total=len(archives))

    def _get_subdirectories(self, path: str) -> List[str]:
        return [str(p) for p in Path(path).iterdir() if p.is_dir()]

    async def _process_dirs_batch(self, directory: str) -> DirsBatchResult:
        dirs = self._get_subdirectories(directory)
        if not dirs:
            raise DirNotFount()

        tasks = [asyncio.create_task(self._process_single_dir(d)) for d in dirs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        fixed: List[BaseAccountProcessingResult] = []
        for r in results:
            if isinstance(r, Exception):
                self.logger.exception("Ошибка при обработке директории", exc_info=r)
            else:
                fixed.append(r)

        return DirsBatchResult(items=fixed, total=len(dirs))

    async def _process_single_dir(self, directory: str) -> BaseAccountProcessingResult:
        result = BaseAccountProcessingResult(valid=False, dir_path=directory)

        try:
            user = await self.tg_client.validate(directory)
            if user:
                result.valid = True
                result.user = user
                result.phone = user.phone
                self.logger.info(f"Аккаунт валиден: {directory}")
            else:
                self.logger.warning(f"Аккаунт НЕ валиден: {directory}")

        except Exception as e:
            self.logger.exception(f"Ошибка при обработке директории: {directory}", exc_info=e)

        return result

    async def _process_single_archive(self, archive_path: str) -> ArchiveProcessingResult:
        result = ArchiveProcessingResult(
            valid=False,
            archive_path=archive_path,
            user=None,
            dir_path=None
        )

        temp_dir = None

        async with SEM:
            try:
                self.logger.info(f"Обработка архива: {archive_path}")

                temp_dir = await extract_archive_to_temp(archive_path)
                result.dir_path = temp_dir

                user = await self.tg_client.validate(temp_dir)

                if user:
                    result.valid = True
                    result.user = user
                    result.phone = user.phone
                    self.logger.info(f"Аккаунт валиден: {archive_path}")
                else:
                    self.logger.warning(f"Невалидный аккаунт: {archive_path}")

            except Exception as e:
                self.logger.exception(f"Ошибка в архиве {archive_path}", exc_info=e)
                if temp_dir:
                    shutil.rmtree(temp_dir)

        return result