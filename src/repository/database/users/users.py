from typing import Optional, Sequence

from sqlalchemy import func, select, update

from src.database.models.users import Users
from src.repository.database.base import DatabaseBase


class UsersRepository(DatabaseBase):
    async def get_by_id(self, user_id: int) -> Optional[Users]:
        result = await self.session_db.execute(
            select(Users).where(Users.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> Optional[Users]:
        result = await self.session_db.execute(
            select(Users).where(Users.unique_referral_code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Sequence[Users]:
        result = await self.session_db.execute(
            select(Users).where(Users.username == username)
        )
        return result.scalars().all()

    async def count_all(self) -> int:
        result = await self.session_db.execute(select(func.count()).select_from(Users))
        return int(result.scalar() or 0)

    async def create_user(self, **values) -> Users:
        return await super().create(Users, **values)

    async def update(self, user_id: int, **values) -> Optional[Users]:
        if not values:
            return await self.get_by_id(user_id)

        stmt = (
            update(Users)
            .where(Users.user_id == user_id)
            .values(**values)
            .returning(Users)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()