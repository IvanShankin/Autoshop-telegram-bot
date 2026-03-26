from typing import Dict

from pydantic import BaseModel


class CreateAdminAction(BaseModel):
    action_type: str
    message: str
    details: Dict