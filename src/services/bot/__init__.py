from src.services.bot.edit_message import EditMessageService
from src.services.bot.mass_tg_mailng import MassTgMailingService
from src.services.bot.send_files import SendFileService
from src.services.bot.send_log import SendLogs
from src.services.bot.send_message import SendMessageService
from src.services.bot.sticker_sender import StickerSender


class Messages:

    def __init__(
        self,
        send_msg: SendMessageService,
        edit_msg: EditMessageService,
        mass_tg_mailing: MassTgMailingService,
        send_file: SendFileService,
        send_log: SendLogs,
        sticker_sender: StickerSender,
    ):
        self.send_msg = send_msg
        self.edit_msg = edit_msg
        self.mass_tg_mailing = mass_tg_mailing
        self.send_file = send_file
        self.send_log = send_log
        self.sticker_sender = sticker_sender
