from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.models.systems import UiImagesService
from src.models.read_models.admins import MessageForSendingDTO
from src.models.update_models import UpdateUiImageDTO
from src.models.update_models.admins import UpdateMessageForSending
from src.repository.database.admins import MessageForSendingRepository


class MessageForSendingService:

    def __init__(
        self,
        msg_for_sending_repo: MessageForSendingRepository,
        ui_image_service: UiImagesService,
        session_db: AsyncSession
    ):
        self.msg_for_sending_repo = msg_for_sending_repo
        self.ui_image_service = ui_image_service
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
        file_bytes: Optional[bytes] = None,
        show_image: Optional[bool] = None,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = True,
    ) -> Optional[UpdateMessageForSending]:
        """
        :param filling_redis: используется только при изменении `show_image`
        """
        button_url = data.button_url if not data.button_url is False else False
        values = data.model_dump(exclude_unset=True)
        values["button_url"] = button_url

        settings = await self.msg_for_sending_repo.update_message_for_sending(**values)
        msg: Optional[MessageForSendingDTO] = None

        if show_image is not None:
            msg = await self.get_msg(data.user_id)
            await self.ui_image_service.update_ui_image(
                key=msg.ui_image_key,
                data=UpdateUiImageDTO(show=show_image),
                make_commit=make_commit,
                filling_redis=filling_redis,
            )

        if file_bytes is not None:
            if not msg:
                msg = await self.get_msg(data.user_id)

            await self.ui_image_service.update_file(
                key=msg.ui_image_key,
                file_bytes=file_bytes,
                make_commit=make_commit,
                filling_redis=filling_redis,
            )

        if make_commit:
            await self.session_db.commit()

        return settings

    async def delete_msg(self, user_id: int, make_commit: Optional[bool] = False) -> None:
        await self.msg_for_sending_repo.delete_message_for_sending(user_id)
        if make_commit:
            await self.session_db.commit()
