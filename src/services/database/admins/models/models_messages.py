from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.services.database.core.database import Base


class MessageForSending(Base):
    __tablename__ = "message_for_sending"

    user_id = Column(BigInteger, ForeignKey("users.user_id"), primary_key=True)
    content = Column(Text, nullable=True)
    ui_image_key = Column(String, ForeignKey("ui_images.key"), nullable=False)
    button_url = Column(String(500), nullable=True)

    user = relationship("Users", back_populates="message_for_sending")
    ui_image = relationship("UiImages", back_populates="message_for_sending")

class SentMasMessages(Base):
    __tablename__ = "sent_mas_messages"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False) # это id админа (напрямую не надо т.к. админ может удалиться)
    content = Column(Text, nullable=True)
    photo_path = Column(String(700), nullable=True)
    photo_id = Column(String(700), nullable=True)
    button_url = Column(String(500), nullable=True)
    number_received = Column(Integer, nullable=False) # число полученных сообщений (те которые фактически дошли до пользователя)
    number_sent = Column(Integer, nullable=False) # число отправленных сообщений
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="sent_mas_messages")