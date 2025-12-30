import os
import shutil
import tempfile
from typing import AsyncGenerator

from src.config import MAX_UPLOAD_FILE
from src.services.accounts.utils.helper_upload import get_account_storage_by_category_id
from src.services.filesystem.account_actions import decryption_tg_account
from src.services.filesystem.actions import get_dir_size, make_archive
from src.services.secrets import get_crypto_context


async def upload_tg_account(category_id: int) -> AsyncGenerator[str, str]:
    """
    :param category_id:
    :return:
    :raise ProductAccountNotFound: Если категория не хранит аккаунты.
    Просто не нашли аккаунты это может быть и связанно с тем что категория не имеет флаг is_account_storage
    """
    i = 0
    current_chunk_files = []
    current_chunk_size = 0
    temp_dir = tempfile.mkdtemp()

    accounts = await get_account_storage_by_category_id(category_id)

    for acc in accounts:
        crypto = get_crypto_context()
        decrypted_folder = decryption_tg_account(acc.account_storage, crypto)
        folder_size = get_dir_size(decrypted_folder)

        # обрабатывать слишком большие директории (которые превышают MAX_UPLOAD_FILE 49 мб) не надо
        # т.к. мы можем принять максимум MAX_DOWNLOAD_SIZE (20 мб)

        if current_chunk_size + folder_size > MAX_UPLOAD_FILE:
            # дошли до предела по размеру файла -> формируем архив и возвращаем путь
            archive_path = os.path.join(temp_dir, f"account_chunk_{i}.zip")
            await make_archive(current_chunk_files, archive_path)
            yield archive_path
            os.remove((archive_path)) # удаление

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
        os.remove(archive_path) # удаление

    shutil.rmtree(temp_dir)

