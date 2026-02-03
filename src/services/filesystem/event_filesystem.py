import asyncio

from src.services.database.system.actions import update_ui_image
from src.services.filesystem.actions import get_default_image_bytes
from src.services.filesystem.media_paths import create_path_ui_image
from src.services.filesystem.schemas import EventCreateUiImage
from src.utils.core_logger import get_logger


async def filesystem_event_handler(event):
    payload = event["payload"]

    if event["event"] == "filesystem.create_ui_image":
        obj = EventCreateUiImage.model_validate(payload)
        await handler_create_ui_image(obj)


async def handler_create_ui_image(obj: EventCreateUiImage):
    new_file_name = f"{obj.ui_image_key}.png"
    new_file_path = create_path_ui_image(file_name=new_file_name)

    data = get_default_image_bytes()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: open(new_file_path, "wb").write(data)
    )

    await update_ui_image(obj.ui_image_key, file_name=new_file_name, show=False, file_id=None)

    get_logger(__name__).info(f"Создали новое изображение для ui_image: {obj.ui_image_key}")
