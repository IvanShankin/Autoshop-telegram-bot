from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.read_models.admins import MessageForSendingDTO
from src.models.update_models.admins import UpdateMessageForSending
from src.repository.database.admins import MessageForSendingRepository


class MessageForSendingService:

    def __init__(self, msg_for_sending_repo: MessageForSendingRepository, session_db: AsyncSession):
        self.msg_for_sending_repo = msg_for_sending_repo
        self.session_db = session_db

    async def create_msg(
        self, user_id: int, ui_image_key: str, make_commit: Optional[bool] = False
    ) -> MessageForSendingDTO:
        msg = await self.msg_for_sending_repo.create_message_for_sending(user_id, ui_image_key)
        if make_commit:
            await self.session_db.commit()

        return msg

    async def get_msg(self, user_id: int) -> MessageForSendingDTO:
        return await self.msg_for_sending_repo.get_message_for_sending(user_id)

    async def update_msg(
        self,
        data: UpdateMessageForSending,
        make_commit: Optional[bool] = False,
    ) -> Optional[UpdateMessageForSending]:
        values = data.model_dump(exclude_unset=True)
        settings = await self.msg_for_sending_repo.update_message_for_sending(**values)

        if make_commit:
            await self.session_db.commit()

        return settings

    async def delete_msg(self, user_id: int, make_commit: Optional[bool] = False) -> None:
        await self.msg_for_sending_repo.delete_message_for_sending(user_id)
        if make_commit:
            await self.session_db.commit()
