import os.path
from pathlib import Path

from src.services.filesystem.event_filesystem import handler_create_ui_image
from src.services.filesystem.media_paths import create_path_ui_image
from src.services.filesystem.schemas import EventCreateUiImage


async def test_handler_create_ui_image(create_ui_image):
    ui_image, path_file = await create_ui_image()
    event_data = EventCreateUiImage(ui_image_key = ui_image.key)

    path_obj = Path(path_file)
    path_obj.unlink(missing_ok=True)

    old_file_path = create_path_ui_image(file_name=ui_image.file_name)
    assert not os.path.isfile(old_file_path)

    await handler_create_ui_image(event_data)

    new_file_name = f"{ui_image.key}.png"
    new_file_path = create_path_ui_image(file_name=new_file_name)

    assert os.path.isfile(new_file_path)