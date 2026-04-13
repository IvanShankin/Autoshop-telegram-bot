import os
import shutil
from logging import Logger
from pathlib import Path

from src.application.crypto.crypto_context import CryptoProvider
from src.application.events.publish_event_handler import PublishEventHandler
from src.database.models.categories import StorageStatus
from src.infrastructure.files.file_system import move_file
from src.infrastructure.files.path_builder import PathBuilder
from src.models.read_models import UniversalStoragePydantic


class UniversalProduct:

    def __init__(
        self,
        crypto_provider: CryptoProvider,
        path_builder: PathBuilder,
        publish_event_handler: PublishEventHandler,
        logger: Logger,
    ):
        self.crypto_provider = crypto_provider
        self.path_builder = path_builder
        self.publish_event_handler = publish_event_handler
        self.logger = logger


    async def move_universal_storage(
        self,
        storage: UniversalStoragePydantic,
        new_status: StorageStatus
    ) -> Path | bool:
        """
        Перенос аккаунтов к `status` удалив исходное местоположение.
        :param status: Статус товара который будет в конечном пути
        :return: Если возникнет ошибка или аккаунт не переместится, то вернёт False
        """
        orig = None
        final = None
        try:
            orig = self.path_builder.build_path_universal_storage(
                status=storage.status,
                uuid=storage.storage_uuid,
                as_path=True
            )
            final = self.path_builder.build_path_universal_storage(
                status=new_status,
                uuid=storage.storage_uuid,
                as_path=True
            )

            moved = await move_file(str(orig), str(final))
            if not moved:
                return False

            # Удаление директории где хранится аккаунт (uui). Директория уже будет пустой
            if os.path.isdir(str(orig.parent)):
                shutil.rmtree(str(orig.parent))

            return final
        except Exception as e:
            text = (
                f"#Ошибка при переносе универсального товара к {new_status}. \n"
                f"Исходный путь: {str(orig) if str(orig) else "none"} \n"
                f"Финальный путь: {str(final) if str(final) else "none"} \n"
                f"account_storage_id: {storage.universal_storage_id if storage.universal_storage_id else "none"} \n"
                f"Ошибка: {str(e)}"
            )
            self.logger.exception(
                f"Ошибка при переносе универсального товара к {new_status} %s",
                     storage.universal_storage_id
            )

            await self.publish_event_handler.send_log(text)

            return False

