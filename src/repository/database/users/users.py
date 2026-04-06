from typing import Optional, Sequence, AsyncGenerator, List

from sqlalchemy import func, select, update

from src.database.models.users import Users
from src.models.read_models.other import UsersDTO
from src.repository.database.base import DatabaseBase


class UsersRepository(DatabaseBase):

    async def get_by_ids(self, user_ids: List[int]) -> List[UsersDTO]:
        result = await self.session_db.execute(
            select(Users).where(Users.user_id.in_(user_ids))
        )
        users = result.scalars()
        return [UsersDTO.model_validate(user) for user in users]

    async def get_by_id(self, user_id: int) -> Optional[UsersDTO]:
        result = await self.session_db.execute(
            select(Users).where(Users.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        return UsersDTO.model_validate(user) if user else None

    async def get_by_id_for_update(self, user_id: int) -> Optional[Users]:
        result = await self.session_db.execute(
            select(Users)
            .where(Users.user_id == user_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

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

    async def gen_user_ids(self) -> AsyncGenerator[int, None]:
        result = await self.session_db.stream_scalars(select(Users.user_id))
        async for uid in result:
            yield uid

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

    async def update_balance_by_delta(self, user_id: int, delta: int) -> Optional[UsersDTO]:
        result = await self.session_db.execute(
            update(Users)
            .where(Users.user_id == user_id)
            .values(balance=Users.balance + delta)
            .returning(Users)
        )
        updated = result.scalar_one_or_none()
        return UsersDTO.model_validate(updated) if updated else None
