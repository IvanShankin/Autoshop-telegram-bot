from typing import Optional, Sequence

from sqlalchemy import func, select, update

from src.database.models.users import Users
from src.read_models.other import UsersDTO
from src.repository.database.base import DatabaseBase


class UsersRepository(DatabaseBase):
    async def get_by_id(self, user_id: int) -> Optional[UsersDTO]:
        result = await self.session_db.execute(
            select(Users).where(Users.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        return UsersDTO.model_validate(user) if user else None

    async def get_by_referral_code(self, code: str) -> Optional[UsersDTO]:
        result = await self.session_db.execute(
            select(Users).where(Users.unique_referral_code == code)
        )
        user = result.scalar_one_or_none()
        return UsersDTO.model_validate(user) if user else None

    async def get_by_username(self, username: str) -> Sequence[UsersDTO]:
        result = await self.session_db.execute(
            select(Users).where(Users.username == username)
        )
        users = list(result.scalars().all())
        return [UsersDTO.model_validate(user) for user in users]

    async def count_all(self) -> int:
        result = await self.session_db.execute(select(func.count()).select_from(Users))
        return int(result.scalar() or 0)

    async def create_user(self, **values) -> UsersDTO:
        created = await super().create(Users, **values)
        return UsersDTO.model_validate(created)

    async def update(self, user_id: int, **values) -> Optional[UsersDTO]:
        if not values:
            return await self.get_by_id(user_id)

        stmt = (
            update(Users)
            .where(Users.user_id == user_id)
            .values(**values)
            .returning(Users)
        )
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return UsersDTO.model_validate(updated) if updated else None
