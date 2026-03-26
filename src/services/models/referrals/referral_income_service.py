from typing import Optional, Sequence

from src.models.read_models.other import IncomeFromReferralsDTO
from src.repository.database.refferals import ReferralIncomeRepository


class ReferralIncomeService:

    def __init__(self, income_repo: ReferralIncomeRepository):
        self.income_repo = income_repo

    async def get_referral_income_page(
        self,
        user_id: int,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Sequence[IncomeFromReferralsDTO]:
        return await self.income_repo.get_page_by_owner(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

    async def get_count_referral_income(self, user_id: int) -> int:
        return await self.income_repo.count_by_owner(user_id)

    async def get_income_from_referral(
        self,
        income_from_referral_id: int,
    ) -> Optional[IncomeFromReferralsDTO]:
        return await self.income_repo.get_by_id(income_from_referral_id)
