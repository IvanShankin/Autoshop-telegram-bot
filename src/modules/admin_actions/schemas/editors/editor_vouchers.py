from datetime import datetime

from pydantic import BaseModel


class CreateAdminVoucherData(BaseModel):
    number_of_activations: int = None
    expire_at: datetime = None
