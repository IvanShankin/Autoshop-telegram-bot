from typing import List, Optional
from pydantic import BaseModel
from telethon.tl.types import User


class BaseAccountProcessingResult(BaseModel):
    valid: bool
    user: Optional[User] = None
    dir_path: Optional[str] = None

    model_config = {
        "arbitrary_types_allowed": True
    }


class ArchiveProcessingResult(BaseAccountProcessingResult):
    archive_path: str


class DirsBatchResult(BaseModel):
    items: List[BaseAccountProcessingResult]
    total: int


class ArchivesBatchResult(BaseModel):
    items: List[ArchiveProcessingResult]
    total: int


class ImportResult(BaseModel):
    successfully_added: int
    total_processed: int
    invalid_archive_path: Optional[str] = None
    duplicate_archive_path: Optional[str] = None


class CreatedEncryptedArchive(BaseModel):
    result: bool
    encrypted_key_b64: Optional[str] = None
    path_encrypted_acc: Optional[str] = None
    encrypted_key_nonce: Optional[str] = None
    checksum: Optional[str] = None