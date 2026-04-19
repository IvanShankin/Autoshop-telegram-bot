from typing import Optional, Sequence, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.referrals import Referrals
from src.database.models.users import Users
from src.exceptions import InvalidAmountOfAchievement, InvalidSelectedLevel
from src.exceptions.business import InvalidPercent
from src.models.create_models.referrals import CreateReferralLevelDTO
from src.models.read_models.other import ReferralLevelsDTO
from src.models.update_models.referrals import UpdateReferralLevelDTO
from src.repository.database.referrals import ReferralLevelsRepository
from src.repository.redis import ReferralLevelsCacheRepository


class ReferralLevelsService:

    def __init__(
        self,
        referral_lvl_repo: ReferralLevelsRepository,
        cache_repo: ReferralLevelsCacheRepository,
        session_db: AsyncSession,
    ):
        self.referral_lvl_repo = referral_lvl_repo
        self.cache_repo = cache_repo
        self.session_db = session_db

    async def _filling_default_levels(self):
        await self.add_referral_lvl(
            data=CreateReferralLevelDTO(amount_of_achievement=0, percent=3)
        )
        await self.add_referral_lvl(
            data=CreateReferralLevelDTO(amount_of_achievement=2000, percent=4)
        )

    async def get_referral_levels(self) -> Sequence[ReferralLevelsDTO]:
        """Вернёт ReferralLevels отсортированный по возрастанию level"""
        cached = await self.cache_repo.get()
        if cached:
            return sorted(cached, key=lambda x: x.level)

        levels = await self.referral_lvl_repo.get_all()
        if levels:
            await self.cache_repo.set(list(levels))
            return levels

        await self._filling_default_levels()
        levels = await self.referral_lvl_repo.get_all()
        if levels:
            await self.cache_repo.set(list(levels))
        return levels

    async def get_levels_nearby(
        self,
        ref_lvl_id: int,
    ) -> Tuple[Optional[ReferralLevelsDTO], Optional[ReferralLevelsDTO], Optional[ReferralLevelsDTO]]:
        """
        :return: Tuple[Уровень перед искомым, искомый уровень, уровень за искомым]
        """
        levels = await self.get_referral_levels()

        previous_lvl = None
        current_lvl = None
        next_lvl = None

        for lvl in levels:
            if current_lvl is not None:
                next_lvl = lvl
                break

            if lvl.referral_level_id == ref_lvl_id:
                current_lvl = lvl
            else:
                previous_lvl = lvl

        return previous_lvl, current_lvl, next_lvl

    async def add_referral_lvl(self, data: CreateReferralLevelDTO) -> ReferralLevelsDTO:
        """
        Уровень присвоится следующий от максимального (+ 1)
        :except InvalidAmountOfAchievement: При некорректном ``amount_of_achievement``
        :except InvalidPercent: Если ``percent`` более 100.
        """
        ref_lvls = await self.get_referral_levels()
        last_lvl = ref_lvls[-1]

        if data.amount_of_achievement <= last_lvl.amount_of_achievement:
            raise InvalidAmountOfAchievement(
                amount_of_achievement_previous_lvl=last_lvl.amount_of_achievement
            )

        if data.percent > 100:
            raise InvalidPercent()

        new_ref_lvl = await self.referral_lvl_repo.create_referral_lvl(
            level=last_lvl.level + 1,
            amount_of_achievement=data.amount_of_achievement,
            percent=data.percent,
        )

        subquery = (
            select(Users.user_id)
            .where(Users.total_sum_replenishment >= data.amount_of_achievement)
        )

        await self.session_db.execute(
            update(Referrals)
            .where(Referrals.referral_id.in_(subquery))
            .values(level=new_ref_lvl.level)
        )
        await self.session_db.commit()

        levels = await self.referral_lvl_repo.get_all()
        await self.cache_repo.set(list(levels))

        return new_ref_lvl

    async def update_referral_lvl(
        self,
        ref_lvl_id: int,
        data: UpdateReferralLevelDTO,
    ) -> Optional[ReferralLevelsDTO]:
        """
        :except InvalidAmountOfAchievement: При некорректном ``amount_of_achievement``
        :except InvalidPercent: Если ``percent`` более 100.
        """
        values = data.model_dump(exclude_unset=True)
        if not values:
            return None

        current_lvl = await self.referral_lvl_repo.get_by_id(ref_lvl_id)
        if not current_lvl:
            return None

        amount_of_achievement = values.get("amount_of_achievement")
        if current_lvl.level == 1 and amount_of_achievement is not None:
            raise InvalidSelectedLevel()

        percent = values.get("percent")
        if percent > 100:
            raise InvalidPercent()

        previous_lvl = None
        next_lvl = None

        if amount_of_achievement is not None:
            levels = await self.get_referral_levels()
            for lvl in levels:
                if current_lvl.level - 1 == lvl.level:
                    previous_lvl = lvl
                if current_lvl.level + 1 == lvl.level:
                    next_lvl = lvl

            if (
                previous_lvl and amount_of_achievement <= previous_lvl.amount_of_achievement
                or next_lvl and amount_of_achievement >= next_lvl.amount_of_achievement
            ):
                raise InvalidAmountOfAchievement(
                    amount_of_achievement_previous_lvl=previous_lvl.amount_of_achievement if previous_lvl else None,
                    amount_of_achievement_next_lvl=next_lvl.amount_of_achievement if next_lvl else None,
                )

        updated = await self.referral_lvl_repo.update_referral_lvl(ref_lvl_id, **values)
        await self.session_db.commit()

        if amount_of_achievement is not None and previous_lvl:
            subquery = (
                select(Users.user_id)
                .where(Users.total_sum_replenishment < amount_of_achievement)
            )

            await self.session_db.execute(
                update(Referrals)
                .where(Referrals.referral_id.in_(subquery))
                .values(level=previous_lvl.level)
            )
            await self.session_db.commit()

        levels = await self.referral_lvl_repo.get_all()
        await self.cache_repo.set(list(levels))

        return updated

    async def delete_referral_lvl(self, ref_lvl_id: int) -> Optional[ReferralLevelsDTO]:
        previous_lvl, _, _ = await self.get_levels_nearby(ref_lvl_id)
        if previous_lvl is None:
            raise InvalidSelectedLevel()

        deleted = await self.referral_lvl_repo.delete_referral_lvl(ref_lvl_id)
        await self.referral_lvl_repo.update_referral_lvl_after_removal(deleted.level)
        await self.session_db.commit()

        levels = await self.referral_lvl_repo.get_all()
        await self.cache_repo.set(list(levels))

        return deleted
