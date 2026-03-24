from typing import Optional

from pydantic import BaseModel


class ItemForRedis(BaseModel):
    key: str
    value: bytes
    ttl: Optional[int] = None
