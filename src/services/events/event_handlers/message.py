from src.bot_actions.messages.schemas import EventSentLog
from src.services.bot.send_log import SendLogs


class MessageEventHandler:

    def __init__(
        self,
        send_log: SendLogs
    ):
        self.send_log = send_log

    async def message_event_handler(self, event):
        payload = event["payload"]

        if event["event"] == "message.send_log":
            obj = EventSentLog.model_validate(payload)
            await self.send_log.send_log(
                text=obj.text,
                log_lvl=obj.log_lvl,
            )