from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.users import CreateUserAuditLogDTO
from src.models.read_models.other import ReferralsDTO
from src.repository.database.refferals import ReferralsRepository
from src.services.models.referrals.referral_lvls_service import ReferralLevelsService
from src.services.models.users.user_log_service import UserLogService


class ReferralService:

    def __init__(
        self,
        referral_repo: ReferralsRepository,
        referral_lvls_service: ReferralLevelsService,
        log_service: UserLogService,
        session_db: AsyncSession,
    ):
        self.referral_repo = referral_repo
        self.referral_lvls_service = referral_lvls_service
        self.log_service = log_service
        self.session_db = session_db

    async def get_all_referrals(self, user_id: int) -> Sequence[ReferralsDTO]:
        return await self.referral_repo.get_all_by_owner(user_id)

    async def get_referral(self, referral_id: int) -> Optional[ReferralsDTO]:
        return await self.referral_repo.get_by_referral_id(referral_id)

    async def add_referral(self, referral_id: int, owner_id: int) -> ReferralsDTO:
        ref_lvls = await self.referral_lvls_service.get_referral_levels()
        min_level = min(ref_lvls, key=lambda x: x.level)

        async with self.session_db.begin():
            referral = await self.referral_repo.create_referral(
                referral_id=referral_id,
                owner_user_id=owner_id,
                level=min_level.level,
            )

            await self.log_service.create_log(
                user_id=owner_id,
                data=CreateUserAuditLogDTO(
                    action_type="new_referral",
                    message="У пользователя новый реферал",
                    details={"referral_id": referral_id},
                ),
            )
            await self.log_service.create_log(
                user_id=referral_id,
                data=CreateUserAuditLogDTO(
                    action_type="became_referral",
                    message="Пользователь стал рефералом",
                    details={"owner_id": owner_id},
                ),
            )
            await self.session_db.commit()

        return referral
