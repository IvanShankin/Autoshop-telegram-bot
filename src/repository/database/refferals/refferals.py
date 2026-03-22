from typing import Optional, Sequence

from sqlalchemy import select, update

from src.database.models.referrals import Referrals
from src.repository.database.base import DatabaseBase


class ReferralsRepository(DatabaseBase):

    async def get_all_by_owner(self, user_id: int) -> Sequence[Referrals]:
        stmt = (
            select(Referrals)
            .where(Referrals.owner_user_id == user_id)
            .order_by(Referrals.created_at.desc())
        )
        result = await self.session_db.execute(stmt)
        return result.scalars().all()

    async def get_by_referral_id(self, referral_id: int) -> Optional[Referrals]:
        stmt = select(Referrals).where(Referrals.referral_id == referral_id)
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_referral(self, **values) -> Referrals:
        return await super().create(Referrals, **values)

    async def update_level(self, referral_id: int, level: int) -> Optional[Referrals]:
        stmt = (
            update(Referrals)
            .where(Referrals.referral_id == referral_id)
            .values(level=level)
            .returning(Referrals)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()