from pydantic import BaseModel

class TransferData(BaseModel):
    amount: int
    recipient_id: int

class CreateVoucherData(BaseModel):
    amount: int
    number_of_activations: int