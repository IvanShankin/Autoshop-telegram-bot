from typing import Dict

from pydantic import BaseModel


class CreateAdminAction(BaseModel):
    action_type: str
    message: str
    details: Dict


class CreateSentMassMessages(BaseModel):
    content: str
    photo_path: str
    photo_id: str
    button_url: str
    number_received: int  # число полученных сообщений (те которые фактически дошли до пользователя)
    number_sent: int # число отправленных сообщений