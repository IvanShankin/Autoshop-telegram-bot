from typing import Optional

from pydantic import BaseModel

from src.database.models.categories import AccountServiceType, StorageStatus


class CreateAccountStorageDTO(BaseModel):
    is_file: bool
    type_account_service: AccountServiceType
    checksum: str                               # Контроль целостности (SHA256 зашифрованного файла)
    encrypted_key: str                          # Персональный ключ аккаунта, зашифрованный мастер-ключом (DEK)
    encrypted_key_nonce: str                    # nonce, использованный при wrap (Nonce (IV) для AES-GCM (base64))
    phone_number: str                           # номер телефона

    status: StorageStatus = StorageStatus.FOR_SALE
    key_version: int = 1                        # Номер мастер-ключа (для ротации)
    encryption_algo: str = "AES-GCM-256"        # Алгоритм шифрования

    login_encrypted: Optional[str] = None       # Зашифрованный логин
    login_nonce: Optional[str] = None           # используемый nonce при шифровании
    password_encrypted: Optional[str] = None    # Зашифрованный Пароль
    password_nonce: Optional[str] = None        # используемый nonce при шифровании
    tg_id: Optional[int] = None                 # ID аккаунта в телеграмме. Только для ТГ аккаунтов


class CreateProductAccountDTO(BaseModel):
    category_id: int
    account_storage_id: int


class CreateSoldAccountDTO(BaseModel):
    owner_id: int
    account_storage_id: int


class CreateSoldAccountTranslationDTO(BaseModel):
    sold_account_id: int
    language: str
    name: str
    description: Optional[str] = None


class CreateSoldAccountWithTranslationDTO(BaseModel):
    owner_id: int
    account_storage_id: int
    language: str
    name: str
    description: Optional[str] = None


class CreateDeletedAccountDTO(BaseModel):
    account_storage_id: int
    category_name: str
    description: Optional[str] = None


class CreateTgAccountMediaDTO(BaseModel):
    account_storage_id: int
    tdata_tg_id: Optional[str] = None
    session_tg_id: Optional[str] = None
