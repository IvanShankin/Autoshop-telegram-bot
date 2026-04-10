import uuid
from typing import Optional, Sequence

import aiofiles

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.read_models.other import UiImagesDTO
from src.models.update_models.system import UpdateUiImageDTO
from src.repository.database.systems import UiImagesRepository
from src.repository.redis import UiImagesCacheRepository
from src.infrastructure.files.file_system import get_ext_image, get_default_image_bytes
from src.infrastructure.files._media_paths import create_path_ui_image


class UiImagesService:

    def __init__(
        self,
        ui_image_repo: UiImagesRepository,
        cache_repo: UiImagesCacheRepository,
        session_db: AsyncSession,
    ):
        self.ui_image_repo = ui_image_repo
        self.cache_repo = cache_repo
        self.session_db = session_db

    async def create_default_io_image(
        self,
        show: Optional[bool] = False,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> UiImagesDTO:
        file_data = get_default_image_bytes()
        key = str(uuid.uuid4())
        return await self.create_ui_image(
            key=key, file_data=file_data, show=show, make_commit=make_commit, filling_redis=filling_redis
        )

    async def create_ui_image(
        self,
        key: str,
        file_data: bytes,
        show: bool = True,
        file_id: Optional[str] = None,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> UiImagesDTO:
        ext = get_ext_image(file_data)
        file_name = f"{key}.{ext}"

        new_path = create_path_ui_image(file_name=file_name)
        new_path.parent.mkdir(parents=True, exist_ok=True)

        current = await self.ui_image_repo.get_by_key(key)
        if current:
            last_path = create_path_ui_image(file_name=current.file_name)
            last_path.unlink(missing_ok=True)

            async with aiofiles.open(new_path, "wb") as f:
                await f.write(file_data)

            updated = await self.ui_image_repo.update(
                key=key,
                file_name=file_name,
                show=current.show,
                file_id=file_id,
            )
            await self.session_db.commit()

            if updated:
                await self.cache_repo.set(updated)
                return updated

            return current

        async with aiofiles.open(new_path, "wb") as f:
            await f.write(file_data)

        created = await self.ui_image_repo.create_ui_image(
            key=key,
            file_name=file_name,
            file_id=file_id,
            show=show,
        )
        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_repo.set(created)

        return created

    async def get_all_ui_images(self) -> Sequence[UiImagesDTO]:
        return await self.ui_image_repo.get_all()

    async def get_ui_image(self, key: str) -> Optional[UiImagesDTO]:
        cached = await self.cache_repo.get(key)
        if cached:
            return cached

        return await self.ui_image_repo.get_by_key(key)

    async def update_ui_image(
        self,
        key: str,
        data: UpdateUiImageDTO,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> Optional[UiImagesDTO]:
        values = data.model_dump(exclude_unset=True)
        updated = await self.ui_image_repo.update(key=key, **values)

        if make_commit:
            await self.session_db.commit()

        if updated and filling_redis:
            await self.cache_repo.set(updated)

        return updated

    async def delete_ui_image(
        self,
        key: str,
        delete_file: Optional[bool] = True,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> Optional[UiImagesDTO]:
        deleted = await self.ui_image_repo.delete(key=key)

        if make_commit:
            await self.session_db.commit()

        if deleted and delete_file:
            file_path = create_path_ui_image(file_name=deleted.file_name)
            file_path.unlink(missing_ok=True)

        if filling_redis:
            await self.cache_repo.delete(key)

        return deleted
