from typing import Optional

from pydantic import BaseModel

from src.database.models.categories import UniversalMediaType, StorageStatus


class CreateUniversalStorageDTO(BaseModel):
    storage_uuid: Optional[str] = None
    original_filename: Optional[str] = None
    encrypted_tg_file_id: Optional[str] = None
    encrypted_tg_file_id_nonce: Optional[str] = None
    checksum: Optional[str] = None
    encrypted_key: Optional[str] = None
    encrypted_key_nonce: Optional[str] = None
    key_version: int = 1
    encryption_algo: str = "AES-GCM-256"
    media_type: Optional[UniversalMediaType] = None

    status: Optional[StorageStatus] = None # ТЛЬКО ДЛЯ ПОКУПКИ


class CreateUniversalTranslationDTO(BaseModel):
    universal_storage_id: int
    lang: str
    name: str
    encrypted_description: Optional[str] = None
    encrypted_description_nonce: Optional[str] = None


class CreateUniversalStorageWithTranslationDTO(BaseModel):
    language: str
    name: str
    encrypted_description: Optional[str] = None
    encrypted_description_nonce: Optional[str] = None

    storage_uuid: Optional[str] = None
    original_filename: Optional[str] = None
    encrypted_tg_file_id: Optional[str] = None
    encrypted_tg_file_id_nonce: Optional[str] = None
    checksum: Optional[str] = None
    encrypted_key: Optional[str] = None
    encrypted_key_nonce: Optional[str] = None
    key_version: int = 1
    encryption_algo: str = "AES-GCM-256"
    media_type: Optional[UniversalMediaType] = None


class CreateProductUniversalDTO(BaseModel):
    universal_storage_id: int
    category_id: int


class CreateSoldUniversalDTO(BaseModel):
    owner_id: int
    universal_storage_id: int


class CreateDeletedUniversalDTO(BaseModel):
    universal_storage_id: int
