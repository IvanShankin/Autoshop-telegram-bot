from typing import Optional

from pydantic import BaseModel


class UpdateMessageForSending(BaseModel):
    content: Optional[str] = None # текс у будущего сообщения
    file_bytes: Optional[bytes] = None # Поток байт для создания фото
    show_image: Optional[bool] = None
    button_url: Optional[str] = False # можно передать None

