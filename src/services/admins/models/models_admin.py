from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.services.database.database import Base


class Admins(Base):
    __tablename__ = "admins"

    admin_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="admin")

class AdminActions(Base):
    __tablename__ = "admin_actions"

    admin_action_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)  # Кто совершил действие
    action_type = Column(String(100), nullable=False)  # Тип действия (может быть любое)
    details = Column(JSON, nullable=True)  # Гибкое поле для любых деталей
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="admin_actions")