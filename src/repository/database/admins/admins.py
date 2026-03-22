from typing import Optional

from sqlalchemy import select, delete

from src.database.models.admins import (
    Admins,
)


class AdminsRepository:

    async def get_admin_by_user_id(self, user_id: int) -> Optional[Admins]:
        result = await self.session_db.execute(
            select(Admins).where(Admins.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def exists_admin(self, user_id: int) -> bool:
        result = await self.session_db.execute(
            select(Admins.user_id).where(Admins.user_id == user_id)
        )
        return result.scalar_one_or_none() is not None

    async def create_admin(self, user_id: int) -> Admins:
        admin = Admins(user_id=user_id)
        self.session_db.add(admin)
        await self.session_db.flush()  # чтобы получить id без commit
        return admin

    async def delete_admin(self, user_id: int) -> None:
        await self.session_db.execute(
            delete(Admins).where(Admins.user_id == user_id)
        )



