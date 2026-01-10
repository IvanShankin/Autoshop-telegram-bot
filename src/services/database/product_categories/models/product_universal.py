from sqlalchemy import Column, String, ForeignKey, Integer
from sqlalchemy.orm import relationship

from src.services.database.core.database import Base


class ProductUniversal(Base):
    __tablename__ = "product_universal"

    product_universal_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(ForeignKey("products.product_id"))
    tg_file_id = Column(String)
    media_type = Column(String)
    description = Column(String)

    # ПОЗЖЕ ДОБАВИТЬ ЛОКАЛЬНОЕ ЗАШИФРОВАННОЕ ХРАНЕНИЕ
    # ПОЗЖЕ ДОБАВИТЬ ЛОКАЛЬНОЕ ЗАШИФРОВАННОЕ ХРАНЕНИЕ
    # ПОЗЖЕ ДОБАВИТЬ ЛОКАЛЬНОЕ ЗАШИФРОВАННОЕ ХРАНЕНИЕ
    # ПОЗЖЕ ДОБАВИТЬ ЛОКАЛЬНОЕ ЗАШИФРОВАННОЕ ХРАНЕНИЕ

    product = relationship("Products", back_populates="product_universal")
