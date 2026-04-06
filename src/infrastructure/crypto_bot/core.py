from typing import Optional

from aiocryptopay import AioCryptoPay, Networks


class CryptoProvider:
    def __init__(self, client: AioCryptoPay):
        self.client = client

    async def create_invoice(
        self,
        amount_usd: float,
        payload: str,
        expires_in: int
    ) -> tuple[str, str]:
        """
        :return: (invoice_id, invoice_url)
        """
        invoice = await self.client.create_invoice(
            amount=amount_usd,
            currency_type="fiat",
            fiat="USD",
            payload=payload,
            expires_in=expires_in,
        )

        return str(invoice.invoice_id), invoice.bot_invoice_url


crypto_provider: Optional[CryptoProvider] = None


def init_crypto_provider(token: str, testnet: bool = False) -> CryptoProvider:
    global crypto_provider

    crypto_provider = CryptoProvider(
        client=AioCryptoPay(token, network=Networks.TEST_NET if testnet else Networks.MAIN_NET)
    )

    return crypto_provider


def get_crypto_provider() -> CryptoProvider:
    global crypto_provider

    if crypto_provider is None:
        raise RuntimeError("CryptoProvider not initialized")

    return crypto_provider