import hashlib
import hmac
import json
from datetime import datetime

import orjson
import pytest
from aiocryptopay.models.invoice import Invoice

from httpx import AsyncClient, ASGITransport

from src.config import TOKEN_CRYPTO_BOT
from src.services.database.replenishments_event.schemas import NewReplenishment
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_create_invoice_handles_exception(monkeypatch, create_new_user, create_type_payment, replacement_needed_modules, replacement_fake_bot):
    from src.services.payments.crypto_bot.client import CryptoPayService
    user = await create_new_user()
    type_payment = await create_type_payment()

    async with get_redis() as session_redis:
        await session_redis.set("dollar_rate", 80)

    service = CryptoPayService(token="fake", testnet=True)
    fake_bot = replacement_fake_bot

    # Мокаем create_invoice у клиента, чтобы выбрасывал ошибку
    async def raise_error(*a, **kw): raise Exception("Fake error")
    service.client.create_invoice = raise_error

    await service.create_invoice(
        user_id=user.user_id,
        type_payment_id=type_payment.type_payment_id,
        origin_amount_rub=1000,
        amount_rub=1000
    )

    assert fake_bot.check_str_in_messages("#Ошибка_при_создание_счёта_в_КБ")

@pytest.mark.asyncio
async def test_create_invoice_handles(monkeypatch, create_new_user, create_type_payment, replacement_needed_modules, replacement_fake_bot):
    from src.services.payments.crypto_bot.client import CryptoPayService
    user = await create_new_user()
    type_payment = await create_type_payment()

    async with get_redis() as session_redis:
        await session_redis.set("dollar_rate", 80)

    service = CryptoPayService(token="fake", testnet=True)

    # Мокаем create_invoice у клиента
    async def replace_create_invoice(*a, **kw):
        class TestClass:
            invoice_id = 1
            bot_invoice_url = 'example_url'
        return TestClass()
    service.client.create_invoice = replace_create_invoice

    url = await service.create_invoice(
        user_id=user.user_id,
        type_payment_id=type_payment.type_payment_id,
        origin_amount_rub=1000,
        amount_rub=1000
    )
    assert url



# ----- WebHook -----

@pytest.mark.asyncio
async def test_webhook_crypto_bot(monkeypatch, create_new_user, create_replenishment, replacement_needed_modules, replacement_fake_bot):
    from src.services.fastapi_core.server import app
    user = await create_new_user()
    replenishment = await create_replenishment()

    payload = NewReplenishment(
        replenishment_id = replenishment.replenishment_id,
        user_id = user.user_id,
        origin_amount = replenishment.origin_amount,
        amount = replenishment.amount,
    )

    invoice = Invoice(
        invoice_id = 1,
        status = "pending",
        hash = "hash",
        currency_type = "currency_type",
        amount = 100,
        bot_invoice_url = "test_url",
        web_app_invoice_url = "test_url",
        mini_app_invoice_url = "test_url",
        created_at = datetime.now(),
        allow_comments = False,
        allow_anonymous = False,
        payload = json.dumps(payload.model_dump())
    )

    data = {
        "update_id": 123456,
        "update_type": "invoice_paid",
        "request_date": "2025-10-23T00:00:00Z",
        "payload": invoice.model_dump()
    }

    raw_body = orjson.dumps(data)
    secret = hashlib.sha256(TOKEN_CRYPTO_BOT.encode()).digest()
    signature = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as ac:
        response = await ac.post(
            "/crypto/webhook",
            headers={"crypto-pay-api-signature": signature},
            content=raw_body
        )

        assert response.status_code == 200
        assert response.json() == {"result": "ok"}

@pytest.mark.asyncio
async def test_webhook_crypto_bot_missing_signature():
    from src.services.fastapi_core.server import app

    data = {"update_type": "invoice_paid"}
    raw_body = orjson.dumps(data)

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as ac:
        response = await ac.post(
            "/crypto/webhook",
            content=raw_body
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing signature"

@pytest.mark.asyncio
async def test_webhook_crypto_bot_invalid_signature():
    from src.services.fastapi_core.server import app

    data = {"update_type": "invoice_paid"}
    raw_body = orjson.dumps(data)

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as ac:
        response = await ac.post(
            "/crypto/webhook",
            headers={"crypto-pay-api-signature": "wrong_signature"},
            content=raw_body
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid signature"

@pytest.mark.asyncio
async def test_webhook_crypto_bot_no_payload(monkeypatch):
    from src.services.fastapi_core.server import app

    data = {
        "update_id": 1,
        "update_type": "invoice_paid",
        "payload": {"payload": ""}
    }

    raw_body = orjson.dumps(data)
    secret = hashlib.sha256(TOKEN_CRYPTO_BOT.encode()).digest()
    signature = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as ac:
        response = await ac.post(
            "/crypto/webhook",
            headers={"crypto-pay-api-signature": signature},
            content=raw_body
        )

    assert response.status_code == 400

