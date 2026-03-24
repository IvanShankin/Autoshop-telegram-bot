from typing import Optional, Sequence

from sqlalchemy import select, func

from src.database.models.referrals import IncomeFromReferrals
from src.read_models.other import IncomeFromReferralsDTO
from src.repository.database.base import DatabaseBase


class ReferralIncomeRepository(DatabaseBase):

    async def get_page_by_owner(
        self,
        user_id: int,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Sequence[IncomeFromReferralsDTO]:
        if page_size is None:
            page_size = self.conf.different.page_size

        stmt = (
            select(IncomeFromReferrals)
            .where(IncomeFromReferrals.owner_user_id == user_id)
            .order_by(IncomeFromReferrals.created_at.desc())
        )

        if page is not None:
            stmt = stmt.limit(page_size).offset((page - 1) * page_size)

        result = await self.session_db.execute(stmt)
        incomes = list(result.scalars().all())
        return [IncomeFromReferralsDTO.model_validate(income) for income in incomes]

    async def count_by_owner(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(IncomeFromReferrals).where(
            IncomeFromReferrals.owner_user_id == user_id
        )
        result = await self.session_db.execute(stmt)
        return int(result.scalar() or 0)

    async def get_by_id(self, income_from_referral_id: int) -> Optional[IncomeFromReferralsDTO]:
        stmt = select(IncomeFromReferrals).where(
            IncomeFromReferrals.income_from_referral_id == income_from_referral_id
        )
        result = await self.session_db.execute(stmt)
        income = result.scalar_one_or_none()
        return IncomeFromReferralsDTO.model_validate(income) if income else None

    async def get_by_replenishment_id(self, replenishment_id: int) -> Optional[IncomeFromReferralsDTO]:
        stmt = select(IncomeFromReferrals).where(
            IncomeFromReferrals.replenishment_id == replenishment_id
        )
        result = await self.session_db.execute(stmt)
        income = result.scalar_one_or_none()
        return IncomeFromReferralsDTO.model_validate(income) if income else None

    async def create_income(self, **values) -> IncomeFromReferralsDTO:
        created = await super().create(IncomeFromReferrals, **values)
        return IncomeFromReferralsDTO.model_validate(created)
