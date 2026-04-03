from pydantic import BaseModel, ConfigDict


class BaseDTO:
    pass


class ORMDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)