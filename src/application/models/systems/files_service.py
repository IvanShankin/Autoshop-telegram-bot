from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.system import CreateFileDTO
from src.models.read_models.other import FilesDTO
from src.models.update_models.system import UpdateFileDTO
from src.repository.database.systems import FilesRepository


class FilesService:

    def __init__(self, files_repo: FilesRepository, session_db: AsyncSession):
        self.files_repo = files_repo
        self.session_db = session_db

    async def get_file(self, key: str) -> Optional[FilesDTO]:
        return await self.files_repo.get_by_key(key)

    async def create_file(
        self,
        key: str,
        data: CreateFileDTO,
        make_commit: Optional[bool] = False,
    ) -> FilesDTO:
        values = data.model_dump()
        file_obj = await self.files_repo.create_file(key=key, **values)

        if make_commit:
            await self.session_db.commit()

        return file_obj

    async def update_file(
        self,
        key: str,
        file_path: Optional[str] = False,
        file_tg_id: Optional[str] = False,
        make_commit: Optional[bool] = False,
    ) -> Optional[FilesDTO]:
        update_data = {}
        if not file_path is False:
            update_data["file_path"] = file_path
        if not file_tg_id is False:
            update_data["file_tg_id"] = file_tg_id

        file_obj = await self.files_repo.update(key=key, **update_data)

        if make_commit:
            await self.session_db.commit()

        return file_obj

    async def delete_file(
        self,
        key: str,
        make_commit: Optional[bool] = False,
    ) -> Optional[FilesDTO]:
        deleted = await self.files_repo.delete(key=key)

        if make_commit:
            await self.session_db.commit()

        return deleted
