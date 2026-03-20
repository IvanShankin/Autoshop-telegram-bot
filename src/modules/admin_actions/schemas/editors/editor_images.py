from pydantic import BaseModel


class UpdateEventMsgData(BaseModel):
    event_message_key: str
    current_page: int