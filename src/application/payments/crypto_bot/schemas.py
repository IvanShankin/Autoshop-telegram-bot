from aiocryptopay.models.invoice import Invoice
from pydantic import BaseModel


class WebhookCryptoBotDTO(BaseModel):
    update_id: int
    update_type: str
    request_date: str
    payload: Invoice