from typing import Optional

from src.models.create_models.discounts import CreateActivatedPromoCode
from src.models.read_models.other import ActivatedPromoCodesDTO
from src.repository.database.discount import ActivatedPromoCodeRepository


class ActivatedPromoCodesService:

    def __init__(self, activated_repo: ActivatedPromoCodeRepository):
        self.activated_repo = activated_repo

    async def create_activate_promo_code(self, data: CreateActivatedPromoCode) -> ActivatedPromoCodesDTO:
        return await self.activated_repo.create_activate(**(data.model_dump()))

    async def check_activate_promo_code(self, promo_code_id: int, user_id: int) -> bool:
        """
        Проверит, активировал ли пользователь этот.
        :return True если активировал ранее
        """
        return await self.activated_repo.check_activated(
            promo_code_id=promo_code_id,
            user_id=user_id,
        )

    async def get_activated_promo_code(
        self,
        activate_promo_code_id: int,
    ) -> Optional[ActivatedPromoCodesDTO]:
        return await self.activated_repo.get_by_id(activate_promo_code_id)
