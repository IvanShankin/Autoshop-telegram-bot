from pydantic import BaseModel


class GetTypePaymentNameData(BaseModel):
    type_payment_id: int

class GetTypePaymentCommissionData(BaseModel):
    type_payment_id: int