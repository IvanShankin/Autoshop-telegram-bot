from typing import Optional

from pydantic import BaseModel


class UpdateMessageForSending(BaseModel):
    user_id: int
    content: Optional[str] = None # текс у будущего сообщения
    button_url: Optional[str] = False # можно передать None

