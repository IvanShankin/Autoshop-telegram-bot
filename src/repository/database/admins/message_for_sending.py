from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from src.database.models.admins import (
    MessageForSending,
)


class MessageForSendingRepository:

    async def get_message_for_sending(
        self, user_id: int
    ) -> Optional[MessageForSending]:
        result = await self.session_db.execute(
            select(MessageForSending)
            .options(selectinload(MessageForSending.ui_image))
            .where(MessageForSending.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_message_for_sending(
        self, user_id: int, ui_image_key: str
    ) -> MessageForSending:
        entity = MessageForSending(
            user_id=user_id,
            ui_image_key=ui_image_key,
        )
        self.session_db.add(entity)
        await self.session_db.flush()
        return entity

    async def delete_message_for_sending(self, user_id: int) -> None:
        await self.session_db.execute(
            delete(MessageForSending).where(
                MessageForSending.user_id == user_id
            )
        )

    async def update_message_for_sending(
        self,
        user_id: int,
        content: Optional[str] = None,
        ui_image_key: Optional[str] = None,
        button_url: Optional[str] = None,
    ) -> Optional[MessageForSending]:

        update_data = {}

        if content is not None:
            update_data["content"] = content

        if ui_image_key is not None:
            update_data["ui_image_key"] = ui_image_key

        if button_url is not None:
            update_data["button_url"] = button_url

        if not update_data:
            return None

        result = await self.session_db.execute(
            update(MessageForSending)
            .where(MessageForSending.user_id == user_id)
            .values(**update_data)
            .returning(MessageForSending)
        )

        return result.scalar_one_or_none()