from typing import Dict, Optional

from pydantic import BaseModel


class CreateAdminAction(BaseModel):
    action_type: str
    message: str
    details: Dict


class CreateSentMassMessages(BaseModel):
    content: str
    photo_path: Optional[str]
    photo_id: Optional[str]
    button_url: Optional[str]
    number_received: int  # число полученных сообщений (те которые фактически дошли до пользователя)
    number_sent: int # число отправленных сообщений