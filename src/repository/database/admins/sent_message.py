from typing import List, Optional

from sqlalchemy import select, func

from src.database.models.admins import (
    SentMasMessages,
)


class SentMasMessagesRepository:

    async def get_sent_mass_message(
        self, message_id: int
    ) -> Optional[SentMasMessages]:
        result = await self.session_db.execute(
            select(SentMasMessages).where(
                SentMasMessages.message_id == message_id
            )
        )
        return result.scalar_one_or_none()

    async def get_sent_mass_messages(
        self,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> List[SentMasMessages]:

        if not page_size:
            page_size = self.conf.different.page_size

        query = select(SentMasMessages).order_by(
            SentMasMessages.created_at.desc()
        )

        if page:
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)

        result = await self.session_db.execute(query)
        return list(result.scalars().all())

    async def count_sent_mass_messages(self) -> int:
        result = await self.session_db.execute(
            select(func.count()).select_from(SentMasMessages)
        )
        return int(result.scalar() or 0)