from pydantic import BaseModel


class GetServiceNameData(BaseModel):
    service_type_id: int


class RenameServiceData(BaseModel):
    service_id: int