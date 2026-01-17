import enum
import uuid
from typing import Callable, Any, Tuple

from sqlalchemy import Column, String, ForeignKey, Integer, Boolean, text, Text, DateTime, func, BigInteger, Enum
from sqlalchemy.orm import relationship

from src.services.database.core.database import Base


class UniversalMediaType(enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


class ProductUniversal(Base):
    __tablename__ = "product_universal"

    product_universal_id = Column(Integer, primary_key=True, autoincrement=True)
    universal_storage_id = Column(ForeignKey("universal_storage.universal_storage_id"), nullable=False)
    category_id = Column(ForeignKey("categories.category_id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Categories", back_populates="product_universals")
    storage = relationship("UniversalStorage", back_populates="product")


class UniversalStorage(Base):
    """
    Универсальное хранилище файлов universal-продуктов
    """
    __tablename__ = "universal_storage"

    universal_storage_id = Column(Integer, primary_key=True, autoincrement=True)

    storage_uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    # локальное хранение
    file_path = Column(Text, nullable=True)

    # Telegram CDN
    encrypted_tg_file_id = Column(Text, nullable=True)
    encrypted_tg_file_id_nonce = Column(Text, nullable=True)

    # контроль
    checksum = Column(String(64), nullable=False)

    # для зашифрованных файлов
    encrypted_key = Column(Text, nullable=False)
    encrypted_key_nonce = Column(Text, nullable=False)
    key_version = Column(Integer, nullable=False, server_default=text("1"))
    encryption_algo = Column(String(32), nullable=False, server_default=text("'AES-GCM-256'"))

    media_type = Column(
        Enum(
            UniversalMediaType,
            values_callable=lambda x: [e.value for e in x],
            name="universal_media_type"
        ),
        nullable=False
    )

    is_active = Column(Boolean, nullable=False, server_default=text("true")) # логическое удаление
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sold_universal = relationship("SoldUniversal", back_populates="storage")
    product = relationship("ProductUniversal", back_populates="storage")
    translation = relationship("UniversalStorageTranslation", back_populates="storage")


    def _get_field_with_translation(self,field: Callable[[Any], Any], lang: str, fallback: str = None) -> str | None:
        """Вернёт по указанному языку, если такого не найдёт, то вернёт первый попавшийся"""
        for t in self.translation:
            if t.lang == lang:
                return field(t)
        if fallback:
            for t in self.translation:
                if t.lang == fallback:
                    return field(t)
        # вернём первый попавшийся
        if field(self.translation[0]):
            return field(self.translation[0])
        else:
            return None


    def get_name(self, lang: str, fallback: str = None) -> str:
        """Вернёт по указанному языку, если такого не найдёт, то вернёт первый попавшийся"""
        return self._get_field_with_translation(lambda translation: translation.name, lang, fallback)


    def get_description(self, lang: str, fallback: str = None) -> Tuple[str | None, str | None]:
        """
        Вернёт по указанному языку, если такого не найдёт, то вернёт первый попавшийся
        :return (encrypted_description, encrypted_description_nonce)
        """

        desk = self._get_field_with_translation(
            lambda translation: translation.encrypted_description, lang, fallback
        )
        nonce = self._get_field_with_translation(
            lambda translation: translation.encrypted_description_nonce, lang, fallback
        )

        return desk, nonce


class UniversalStorageTranslation(Base):
    """Всегда должна находиться как минимум одна запись для каждого sold_account_id"""
    __tablename__ = "universal_storage_translations"

    universal_storage_translations_id = Column(Integer, primary_key=True, autoincrement=True)
    universal_storage_id = Column(Integer, ForeignKey("universal_storage.universal_storage_id", ondelete="CASCADE"),nullable=False)
    lang = Column(String(8), nullable=False)  # 'ru', 'en'

    name = Column(Text, nullable=False)         # берётся с Categories

    # Устанавливается пользователем для каждого товара своё
    encrypted_description = Column(Text, nullable=True)
    encrypted_description_nonce = Column(Text, nullable=True)

    storage = relationship("UniversalStorage", back_populates="translation")


class SoldUniversal(Base):
    __tablename__ = "sold_universal"

    sold_universal_id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)

    universal_storage_id = Column(ForeignKey("universal_storage.universal_storage_id"), nullable=False)

    sold_at = Column(DateTime(timezone=True), server_default=func.now())

    storage = relationship("UniversalStorage", back_populates="sold_universal")
    user = relationship("Users", back_populates="sold_universal")
