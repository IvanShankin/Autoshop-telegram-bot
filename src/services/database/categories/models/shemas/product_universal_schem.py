from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.services.database.categories.models.product_universal import UniversalMediaType, UniversalStorage, \
    ProductUniversal, SoldUniversal, UniversalStorageStatus


class UniversalStoragePydantic(BaseModel):
    universal_storage_id: int
    storage_uuid: str

    file_path: Optional[str] = None
    original_filename: Optional[str] = None
    encrypted_tg_file_id: Optional[str] = None
    encrypted_tg_file_id_nonce: Optional[str] = None
    checksum: str

    encrypted_key: str
    encrypted_key_nonce: str
    key_version: int
    encryption_algo: str
    status: UniversalStorageStatus
    media_type: UniversalMediaType

    name: str
    encrypted_description: Optional[str] = None
    encrypted_description_nonce: Optional[str] = None

    is_active: bool
    created_at: datetime

    @classmethod
    def from_orm_model(cls, universal_storage: UniversalStorage, language: str):
        """
        :param universal_storage: передавать с подгруженными translation
        """
        encrypted_description, encrypted_description_nonce = universal_storage.get_description(language)

        return cls(
            universal_storage_id=universal_storage.universal_storage_id,
            storage_uuid=universal_storage.storage_uuid,

            file_path=universal_storage.file_path,
            encrypted_tg_file_id=universal_storage.encrypted_tg_file_id,
            encrypted_tg_file_id_nonce=universal_storage.encrypted_tg_file_id_nonce,
            checksum=universal_storage.checksum,

            encrypted_key=universal_storage.encrypted_key,
            encrypted_key_nonce=universal_storage.encrypted_key_nonce,
            key_version=universal_storage.key_version,
            encryption_algo=universal_storage.encryption_algo,

            status=universal_storage.status,
            media_type=universal_storage.media_type,
            name=universal_storage.get_name(language),
            encrypted_description=encrypted_description,
            encrypted_description_nonce=encrypted_description_nonce,

            is_active=universal_storage.is_active,
            created_at=universal_storage.created_at,
        )


class ProductUniversalSmall(BaseModel):
    product_universal_id: int
    universal_storage_id: int
    category_id: int

    created_at: datetime

    @classmethod
    def from_orm_model(cls, product_universal: ProductUniversal):
        return cls(
            product_universal_id=product_universal.product_universal_id,
            universal_storage_id=product_universal.universal_storage_id,
            category_id=product_universal.category_id,
            created_at=product_universal.created_at,
        )


class ProductUniversalFull(BaseModel):
    product_universal_id: int
    universal_storage_id: int
    category_id: int

    created_at: datetime

    universal_storage: UniversalStoragePydantic

    @classmethod
    def from_orm_model(cls, product_universal: ProductUniversal, language: str):
        """
        :param product_universal: передавать с подгруженным storage, который должен быть с погруженными translation
        """
        return cls(
            product_universal_id=product_universal.product_universal_id,
            universal_storage_id=product_universal.universal_storage_id,
            category_id=product_universal.category_id,
            created_at=product_universal.created_at,
            universal_storage=UniversalStoragePydantic.from_orm_model(product_universal.storage, language),
        )


class SoldUniversalSmall(BaseModel):
    sold_universal_id: int
    owner_id: int
    universal_storage_id: int

    name: str

    sold_at: datetime

    @classmethod
    def from_orm_model(cls, sold_universal: SoldUniversal, language: str):
        """
        :param sold_universal: передавать с подгруженным storage, который должен быть с погруженными translation
        """
        return cls(
            sold_universal_id=sold_universal.sold_universal_id,
            owner_id=sold_universal.owner_id,
            universal_storage_id=sold_universal.universal_storage_id,
            sold_at=sold_universal.sold_at,
            name=sold_universal.storage.get_name(language),
        )


class SoldUniversalFull(BaseModel):
    sold_universal_id: int
    owner_id: int
    universal_storage_id: int

    sold_at: datetime

    universal_storage: UniversalStoragePydantic

    @classmethod
    def from_orm_model(cls, sold_universal: SoldUniversal, language: str):
        """
        :param sold_universal: передавать с подгруженным storage, который должен быть с погруженными translation
        """
        return cls(
            sold_universal_id=sold_universal.sold_universal_id,
            owner_id=sold_universal.owner_id,
            universal_storage_id=sold_universal.universal_storage_id,
            sold_at=sold_universal.sold_at,
            universal_storage=UniversalStoragePydantic.from_orm_model(sold_universal.storage, language),
        )


