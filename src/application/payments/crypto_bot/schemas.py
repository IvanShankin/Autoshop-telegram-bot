from aiocryptopay.models.invoice import Invoice
from pydantic import BaseModel


class WebhookCryptoBot(BaseModel):
    update_id: int
    update_type: str
    request_date: str
    payload: Invoice