from typing import Optional

from src.models.create_models.discounts import CreateVoucherActivationsDTO
from src.models.read_models.other import VoucherActivationsDTO
from src.repository.database.discount import VoucherActivationsRepository


class VoucherActivationsService:

    def __init__(self, activations_repo: VoucherActivationsRepository):
        self.activations_repo = activations_repo

    async def create_activate_voucher(self, data: CreateVoucherActivationsDTO) -> VoucherActivationsDTO:
        return await self.activations_repo.create_activation(**(data.model_dump()))

    async def get_activate_voucher(
        self,
        voucher_activation_id: int,
    ) -> Optional[VoucherActivationsDTO]:
        return await self.activations_repo.get_by_id(voucher_activation_id)
