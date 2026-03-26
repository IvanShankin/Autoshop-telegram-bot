from typing import List, Optional

from sqlalchemy import select, func

from src.database.models.admins import (
    SentMasMessages,
)
from src.models.read_models.admins import SentMasMessagesDTO
from src.repository.database.base import DatabaseBase


class SentMasMessagesRepository(DatabaseBase):

    async def get_sent_mass_message(
        self, message_id: int
    ) -> Optional[SentMasMessagesDTO]:
        result = await self.session_db.execute(
            select(SentMasMessages).where(
                SentMasMessages.message_id == message_id
            )
        )
        result_msg = result.scalar_one_or_none()
        return SentMasMessagesDTO.model_validate(result_msg) if result_msg else None

    async def get_sent_mass_messages(
        self,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> List[SentMasMessagesDTO]:

        if not page_size:
            page_size = self.conf.different.page_size

        query = select(SentMasMessages).order_by(
            SentMasMessages.created_at.desc()
        )

        if page:
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)

        result = await self.session_db.execute(query)
        list_msgs = list(result.scalars().all())

        result_lust = []
        for msg in list_msgs:
            result_lust.append(SentMasMessagesDTO.model_validate(msg))

        return result_lust

    async def count_sent_mass_messages(self) -> int:
        result = await self.session_db.execute(
            select(func.count()).select_from(SentMasMessages)
        )
        return int(result.scalar() or 0)