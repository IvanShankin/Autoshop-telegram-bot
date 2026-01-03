from typing import Dict

from pydantic import BaseModel


class GetServiceNameData(BaseModel):
    service_type_id: int


class RenameServiceData(BaseModel):
    service_id: int


class GetDataForCategoryData(BaseModel):
    service_id: int
    parent_id: int | None
    requested_language: str # входить в get_config().app.allowed_langs
    data_name: Dict[str, str] # код языка и по нему имя


class UpdateNameForCategoryData(BaseModel):
    category_id: int
    language: str


class UpdateDescriptionForCategoryData(BaseModel):
    category_id: int
    language: str


class UpdateCategoryOnlyId(BaseModel):
    category_id: int


class ImportAccountsData(BaseModel):
    category_id: int
    type_account_service: str