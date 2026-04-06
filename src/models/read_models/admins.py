from datetime import datetime

from src.models.base import ORMDTO


class AdminsDTO(ORMDTO):
    admin_id: int
    user_id: int
    created_at: datetime


class AdminActionsDTO(ORMDTO):
    admin_action_id: int
    user_id: int                     # Кто совершил действие (ForeignKey users.user_id)
    action_type: str                 # Тип действия (например, "add_balance", "ban_user" и т.д.)
    message: str                     # Описание действия
    details: dict | None             # Гибкое поле для любых деталей
    created_at: datetime


class MessageForSendingDTO(ORMDTO):
    user_id: int                     # ForeignKey users.user_id
    content: str | None              # текст сообщения
    ui_image_key: str                # ForeignKey ui_images.key
    button_url: str | None           # URL для кнопки


class SentMasMessagesDTO(ORMDTO):
    message_id: int
    user_id: int                     # ID админа, который отправил (ForeignKey users.user_id)
    content: str | None              # текст сообщения
    photo_path: str | None           # путь к фото
    photo_id: str | None             # file_id фото
    button_url: str | None           # URL для кнопки
    number_received: int             # число сообщений, которые дошли до пользователя
    number_sent: int                 # число отправленных сообщений
    created_at: datetime