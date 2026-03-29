from src.bot_actions.messages.send_log import send_log
from src.exceptions.domain import StickerNotFound
from src.infrastructure.telegram.client import TelegramClient
from src.services.models.systems import StickersService
from src.utils.core_logger import get_logger


class StickerSender:
    def __init__(
        self,
        tg_client: TelegramClient,
        sticker_service: StickersService
    ):
        self.tg_client = tg_client
        self.sticker_service = sticker_service


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
            await send_log(f"Ошибка при отправки стикера: \n{str(e)}")