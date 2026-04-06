from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.database.models.categories import StorageStatus


class UpdateAccountStorageDTO(BaseModel):
    storage_uuid: Optional[str] = None
    checksum: Optional[str] = None
    status: Optional[StorageStatus] = None
    encrypted_key: Optional[str] = None
    encrypted_key_nonce: Optional[str] = None
    key_version: Optional[int] = None
    encryption_algo: Optional[str] = None
    login_encrypted: Optional[str] = None
    login_nonce: Optional[str] = None
    password_encrypted: Optional[str] = None
    password_nonce: Optional[str] = None
    last_check_at: Optional[datetime] = None
    is_valid: Optional[bool] = None
    is_active: Optional[bool] = None


class UpdateTgAccountMediaDTO(BaseModel):
    tdata_tg_id: Optional[str] = None
    session_tg_id: Optional[str] = None


class UpdateSoldAccountTranslationDTO(BaseModel):
    sold_account_id: int
    lang: str
    name: Optional[str] = None
    description: Optional[str] = None
