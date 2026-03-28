from typing import Optional

from pydantic import BaseModel

from src.database.models.categories import StorageStatus, UniversalMediaType


class UpdateUniversalStorageDTO(BaseModel):
    storage_uuid: Optional[str] = None
    original_filename: Optional[str] = None
    encrypted_tg_file_id: Optional[str] = None
    encrypted_tg_file_id_nonce: Optional[str] = None
    checksum: Optional[str] = None
    encrypted_key: Optional[str] = None
    encrypted_key_nonce: Optional[str] = None
    key_version: Optional[int] = None
    encryption_algo: Optional[str] = None
    status: Optional[StorageStatus] = None
    media_type: Optional[UniversalMediaType] = None
    is_active: Optional[bool] = None


class UpdateUniversalTranslationDTO(BaseModel):
    universal_storage_id: int
    language: str
    name: Optional[str] = None
    encrypted_description: Optional[str] = None
    encrypted_description_nonce: Optional[str] = None
