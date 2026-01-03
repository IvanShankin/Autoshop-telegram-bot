import json
import hmac
import hashlib
from fastapi import Request, HTTPException, APIRouter
from pydantic import ValidationError

from src.broker.producer import publish_event
from src.config import get_config
from src.services.database.users.actions import update_replenishment, get_replenishment
from src.services.payments.crypto_bot.schemas import WebhookCryptoBot


router = APIRouter()

def verify_signature(token: str, raw_body: bytes, signature: str) -> bool:
    """Проверяет подлинность запроса от CryptoBot"""
    secret = hashlib.sha256(token.encode()).digest()
    check_hash = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(check_hash, signature)


@router.post("/crypto/webhook")
async def crypto_webhook(request: Request):
    signature = request.headers.get("crypto-pay-api-signature")
    if not signature:
        raise HTTPException(status_code=403, detail="Missing signature")

    raw_body = await request.body()
    conf = get_config()

    # Проверка подписи
    if not verify_signature(conf.secrets.token_crypto_bot, raw_body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Парсим JSON
    data = json.loads(raw_body)
    try:
        webhook = WebhookCryptoBot(**data)
    except ValidationError:
        raise HTTPException(status_code=400, detail="Bad Request")

    # Если оплата прошла успешно
    if webhook.update_type == "invoice_paid":
        new_replenishment = json.loads(webhook.payload.payload)
        # если кб несколько раз отправил сообщение, он почему-то при повторной отправке не прикрепляет данные тут
        if not new_replenishment:
            return {"result": "not data"}

        replenishment = await get_replenishment(new_replenishment['replenishment_id'])

        await update_replenishment(
            replenishment_id=replenishment.replenishment_id,
            status='processing',
            payment_system_id=replenishment.payment_system_id,
            invoice_url=replenishment.invoice_url,
        )

        # Публикуем событие
        await publish_event(new_replenishment, 'replenishment.new_replenishment')

    return {'result': 'ok'}

