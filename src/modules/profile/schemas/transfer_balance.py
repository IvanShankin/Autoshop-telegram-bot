from pydantic import BaseModel

class TransferData(BaseModel):
    amount: int
    recipient_id: int
