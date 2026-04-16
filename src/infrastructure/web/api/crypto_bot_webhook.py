import json
import hmac
import hashlib
from fastapi import Request, HTTPException, APIRouter, Depends
from pydantic import ValidationError

from src.containers import RequestContainer
from src.application.payments.crypto_bot.schemas import WebhookCryptoBotDTO
from src.infrastructure.web.depends import get_container

router = APIRouter()


def verify_signature(token: str, raw_body: bytes, signature: str) -> bool:
    """Проверяет подлинность запроса от CryptoBot"""
    secret = hashlib.sha256(token.encode()).digest()
    check_hash = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(check_hash, signature)


@router.post("/crypto/webhook")
async def crypto_webhook(
    request: Request,
    container: RequestContainer = Depends(get_container),
):
    signature = request.headers.get("crypto-pay-api-signature")
    if not signature:
        raise HTTPException(status_code=403)

    raw_body = await request.body()

    # конфиг приходит из контейнера
    if not verify_signature(
        container.config.secrets.token_crypto_bot,
        raw_body,
        signature
    ):
        raise HTTPException(status_code=403)

    data = json.loads(raw_body)

    try:
        webhook = WebhookCryptoBotDTO(**data)
    except ValidationError:
        raise HTTPException(status_code=400)

    await container.process_crypto_webhook_use_case.execute(webhook)

    return {"result": "ok"}

