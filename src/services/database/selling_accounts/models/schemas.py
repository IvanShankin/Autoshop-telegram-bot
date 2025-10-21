from typing import List

from pydantic import BaseModel

class PurchaseAccountSchem(BaseModel):
    ids_deleted_product_account: List[int]
    ids_new_sold_account: List[int]