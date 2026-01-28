import os.path
import pytest

from src.services.filesystem.input_universal import generate_example_zip_for_import


@pytest.mark.asyncio
async def test_generate_example_zip_for_import():
    zip_path = await generate_example_zip_for_import()
    assert os.path.isfile(zip_path)
    # Можно не удалять файл, тк он используется в коде