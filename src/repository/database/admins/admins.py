from typing import Optional

from sqlalchemy import select, delete

from src.database.models.admins import (
    Admins,
)
from src.read_models import AdminsDTO
from src.repository.database.base import DatabaseBase


class AdminsRepository(DatabaseBase):

    async def get_admin_by_user_id(self, user_id: int) -> Optional[AdminsDTO]:
        result = await self.session_db.execute(
            select(Admins).where(Admins.user_id == user_id)
        )
        result_admin = result.scalar_one_or_none()
        return AdminsDTO.model_validate(result_admin) if result_admin else None

    async def exists_admin(self, user_id: int) -> bool:
        result = await self.session_db.execute(
            select(Admins.user_id).where(Admins.user_id == user_id)
        )
        return bool(result.scalar_one_or_none()) is not None

    async def create_admin(self, user_id: int) -> AdminsDTO:
        admin = Admins(user_id=user_id)
        self.session_db.add(admin)
        await self.session_db.flush()  # чтобы получить id без commit
        return AdminsDTO.model_validate(admin)

    async def delete_admin(self, user_id: int) -> None:
        await self.session_db.execute(
            delete(Admins).where(Admins.user_id == user_id)
        )



