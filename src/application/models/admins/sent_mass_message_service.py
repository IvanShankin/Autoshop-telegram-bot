from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.admins import CreateSentMassMessages
from src.models.read_models.admins import SentMasMessagesDTO
from src.repository.database.admins import SentMasMessagesRepository


class SentMassMessagesService:

    def __init__(self, sent_msg_repo: SentMasMessagesRepository, session_db: AsyncSession):
        self.sent_msg_repo = sent_msg_repo
        self.session_db = session_db

    async def create_msg(
            self, user_id: int, data: CreateSentMassMessages, make_commit: Optional[bool] = False
    ) -> SentMasMessagesDTO:
        values = data.model_dump()
        msg = await self.sent_msg_repo.create_sent_mass_messages(user_id=user_id, **values)
        if make_commit:
            await self.session_db.commit()

        return msg

    async def get_msg(self, message_id: int) -> SentMasMessagesDTO:
        return await self.sent_msg_repo.get_sent_mass_message(message_id)

    async def get_msgs_by_page(self, page: int = None, page_size: int = None) -> List[SentMasMessagesDTO]:
        return await self.sent_msg_repo.get_sent_mass_messages(page=page, page_size=page_size)

    async def get_count_msgs(self) -> int:
        return await self.sent_msg_repo.count_sent_mass_messages()