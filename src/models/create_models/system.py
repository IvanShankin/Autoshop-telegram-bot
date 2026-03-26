from typing import Optional

from pydantic import BaseModel


class CreateFileDTO(BaseModel):
    file_path: str
    file_tg_id: Optional[str] = None


class CreateStickerDTO(BaseModel):
    file_id: str
    show: bool = True


class CreateUiImageDTO(BaseModel):
    file_name: str
    file_id: Optional[str] = None
    show: bool = True


class CreateBackupLogDTO(BaseModel):
    storage_file_name: str
    storage_encrypted_dek_name: str
    encrypted_dek_b64: str
    dek_nonce_b64: str
    size_bytes: int
