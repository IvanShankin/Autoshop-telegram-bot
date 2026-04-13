from typing import TYPE_CHECKING

from src.exceptions.domain import StickerNotFound
from src.models.read_models.events.message import LogLevel
from src.application.events.publish_event_handler import PublishEventHandler
from src.application.models.systems import StickersService
from src.utils.core_logger import get_logger


if TYPE_CHECKING:
    from src.infrastructure.telegram.bot_client import TelegramClient


class StickerSender:
    def __init__(
        self,
        tg_client: "TelegramClient",
        sticker_service: StickersService,
        publish_event_handler: PublishEventHandler,
    ):
        self.tg_client = tg_client
        self.sticker_service = sticker_service
        self.publish_event_handler = publish_event_handler


    async def send(self, chat_id: int, key: str):
        """
        :except StickerNotFound: Если не найден
        """
        sticker = await self.sticker_service.get_sticker(key)

        if not sticker:
            raise StickerNotFound()

        if not sticker.show or not sticker.file_id:
            return

        try:
            await self.tg_client.send_sticker(
                chat_id=chat_id,
                file_id=sticker.file_id
            )
        except Exception as e:
            logger = get_logger(__name__)
            logger.exception("Ошибка при отправки стикера.\n")
            await self.publish_event_handler.send_log(
                text=f"Ошибка при отправки стикера: \n{str(e)}",
                log_lvl=LogLevel.ERROR,
            )