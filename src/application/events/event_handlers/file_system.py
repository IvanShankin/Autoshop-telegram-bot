import asyncio
from logging import Logger

from src.infrastructure.files.path_builder import PathBuilder
from src.models.read_models import EventCreateUiImage
from src.models.update_models import UpdateUiImageDTO
from src.infrastructure.files.file_system import get_default_image_bytes
from src.application.models.systems import UiImagesService


class FileSystemEventHandler:

    def __init__(
        self,
        path_builder: PathBuilder,
        ui_image_service: UiImagesService,
        logger: Logger
    ):
        self.path_builder = path_builder
        self.ui_image_service = ui_image_service
        self.logger = logger

    async def filesystem_event_handler(self, event):
        payload = event["payload"]

        if event["event"] == "_filesystem.create_ui_image":
            obj = EventCreateUiImage.model_validate(payload)
            await self.handler_create_ui_image(obj)

    async def handler_create_ui_image(self, obj: EventCreateUiImage):
        new_file_name = f"{obj.ui_image_key}.png"
        new_file_path = self.path_builder.build_path_file(file_name=new_file_name)

        data = get_default_image_bytes()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: open(new_file_path, "wb").write(data)
        )

        await self.ui_image_service.update_ui_image(
            obj.ui_image_key,
            data=UpdateUiImageDTO(
                file_name=new_file_name,
                show=False
            ),
        )

        self.logger.info(f"Создали новое изображение для ui_image: {obj.ui_image_key}")