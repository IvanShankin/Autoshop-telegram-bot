import os
import shutil
from typing import AsyncGenerator

from src.application.crypto.crypto_context import CryptoProvider
from src.application.models.products.accounts import AccountProductService
from src.application.products.accounts.account_service import AccountService
from src.config import Config
from src.infrastructure.files.file_system import create_temp_dir, get_dir_size, make_archive


class UploadTGAccountsUseCase:

    def __init__(
        self,
        conf: Config,
        account_service: AccountService,
        account_product_service: AccountProductService,
        crypto_provider: CryptoProvider,
    ):
        self.conf = conf
        self.account_service = account_service
        self.account_product_service = account_product_service
        self.crypto_provider = crypto_provider


    async def execute(self, category_id: int) -> AsyncGenerator[str, str]:
        """
        :param category_id:
        :return:
        :raise ProductAccountNotFound: Если категория не хранит аккаунты.
        Просто не нашли аккаунты это может быть и связанно с тем что категория не имеет флаг is_account_storage
        """
        i = 0
        current_chunk_files = []
        current_chunk_size = 0
        temp_dir = create_temp_dir(self.conf)

        accounts = await self.account_product_service.get_product_accounts_by_category_id(
            category_id,
            get_full=True,
        )

        for acc in accounts:
            crypto = self.crypto_provider.get()
            decrypted_folder = self.account_service.decryption_tg_account(
                acc.account_storage, crypto, acc.account_storage.status
            )
            folder_size = get_dir_size(decrypted_folder)

            # обрабатывать слишком большие директории (которые превышают config.limits.max_upload_file 49 мб) не надо
            # т.к. мы можем принять максимум config.limits.max_download_size (20 мб)

            if current_chunk_size + folder_size > self.conf.limits.max_upload_file:
                # дошли до предела по размеру файла -> формируем архив и возвращаем путь
                archive_path = os.path.join(temp_dir, f"account_chunk_{i}.zip")
                await make_archive(current_chunk_files, archive_path)
                yield archive_path
                os.remove((archive_path))  # удаление

                current_chunk_files = []
                current_chunk_size = 0
                i += 1

            current_chunk_files.append(decrypted_folder)
            current_chunk_size += folder_size

        # если остался неотправленный архив
        if current_chunk_files:
            archive_path = os.path.join(temp_dir, f"account_chunk_{i}.zip")
            await make_archive(current_chunk_files, archive_path)
            yield archive_path
            os.remove(archive_path)  # удаление

        shutil.rmtree(temp_dir)
