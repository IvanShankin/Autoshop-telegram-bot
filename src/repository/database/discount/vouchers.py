from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence, List

from sqlalchemy import func, select, update, and_

from src.database.models.discount import Vouchers
from src.models.read_models.other import VouchersDTO
from src.repository.database.base import DatabaseBase


class VouchersRepository(DatabaseBase):

    async def get_by_id(
        self,
        voucher_id: int,
        *,
        check_on_valid: bool = True,
    ) -> Optional[VouchersDTO]:
        stmt = select(Vouchers).where(Vouchers.voucher_id == voucher_id)

        if check_on_valid:
            stmt = stmt.where(Vouchers.is_valid.is_(True))

        result = await self.session_db.execute(stmt)
        voucher = result.scalar_one_or_none()
        return VouchersDTO.model_validate(voucher) if voucher else None

    async def get_by_code(
        self,
        code: str,
        *,
        only_valid: bool = True,
    ) -> Optional[VouchersDTO]:
        stmt = select(Vouchers).where(Vouchers.activation_code == code)

        if only_valid:
            stmt = stmt.where(Vouchers.is_valid.is_(True))

        result = await self.session_db.execute(stmt)
        voucher = result.scalar_one_or_none()
        return VouchersDTO.model_validate(voucher) if voucher else None

    async def get_valid_by_page(
        self,
        *,
        user_id: Optional[int] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        only_created_admin: bool = False,
    ) -> Sequence[VouchersDTO]:
        if page_size is None:
            page_size = self.conf.different.page_size

        stmt = select(Vouchers).order_by(Vouchers.start_at.desc())

        if only_created_admin:
            stmt = stmt.where(Vouchers.is_created_admin.is_(True))
        else:
            stmt = stmt.where(
                Vouchers.is_valid.is_(True),
                Vouchers.is_created_admin.is_(False),
            )
            if user_id is not None:
                stmt = stmt.where(Vouchers.creator_id == user_id)

        if page is not None:
            offset = (page - 1) * page_size
            stmt = stmt.limit(page_size).offset(offset)

        result = await self.session_db.execute(stmt)
        vouchers = list(result.scalars().all())
        return [VouchersDTO.model_validate(voucher) for voucher in vouchers]

    async def set_not_valid_voucher(self, data_time_to: datetime) -> List[VouchersDTO]:
        """
        Установит is_valid=False у ваучеров где дата меньше чем `data_time_to`
        :return:
        """
        result_db = await self.session_db.execute(
            update(Vouchers)
            .where(
                and_(
                    Vouchers.is_valid.is_(True),
                    Vouchers.expire_at.isnot(None),
                    Vouchers.expire_at <= data_time_to
                )
            )
            .values(is_valid=False)
            .returning(Vouchers)
        )
        vouchers = list(result_db.scalars().all())
        return [VouchersDTO.model_validate(voucher) for voucher in vouchers]

    async def count(
        self,
        *,
        user_id: Optional[int] = None,
        by_admins: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(Vouchers)

        if by_admins:
            stmt = stmt.where(
                Vouchers.is_created_admin.is_(True),
                Vouchers.is_valid.is_(True),
            )
        else:
            stmt = stmt.where(Vouchers.is_valid.is_(True))
            if user_id is not None:
                stmt = stmt.where(Vouchers.creator_id == user_id)

        result = await self.session_db.execute(stmt)
        return int(result.scalar() or 0)

    async def create_voucher(self, **values) -> VouchersDTO:
        created = await super().create(Vouchers, **values)
        return VouchersDTO.model_validate(created)

    async def deactivate(self, voucher_id: int) -> Optional[VouchersDTO]:
        stmt = (
            update(Vouchers)
            .where(Vouchers.voucher_id == voucher_id)
            .values(is_valid=False)
            .returning(Vouchers)
        )
        result = await self.session_db.execute(stmt)
        voucher = result.scalar_one_or_none()
        return VouchersDTO.model_validate(voucher) if voucher else None



    async def increment_activated_counter(self, voucher_id: int) -> Optional[VouchersDTO]:
        stmt = (
            update(Vouchers)
            .where(Vouchers.voucher_id == voucher_id)
            .values(activated_counter=Vouchers.activated_counter + 1)
            .returning(Vouchers)
        )
        result = await self.session_db.execute(stmt)
        voucher = result.scalar_one_or_none()
        return VouchersDTO.model_validate(voucher) if voucher else None
