from src.bot_actions.messages import send_log
from src.bot_actions.messages.schemas import EventSentLog


async def message_event_handler(event):
    payload = event["payload"]

    if event["event"] == "message.send_log":
        obj = EventSentLog.model_validate(payload)
        await send_log(
            text=obj.text,
            log_lvl=obj.log_lvl,
            channel_for_logging_id=obj.channel_for_logging_id
        )