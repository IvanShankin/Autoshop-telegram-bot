from src.application.crypto.crypto_context import CryptoProvider, InitCryptoContext
from src.config import RuntimeConfig
from src.infrastructure.crypto.key_store import KeyStore
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage


def secret_storage_factory() -> SecretsStorage:
    class FakeSecretStorage:
        pass

    return FakeSecretStorage()


def crypto_provider_factory():
    class FakeLogger:
        def info(self, *args, **kwargs):
            pass

    runtime_conf = RuntimeConfig()
    crypto_provider = CryptoProvider()
    init_crypto_context = InitCryptoContext(
        storage=secret_storage_factory(),
        keystore=KeyStore(),
        logger=FakeLogger(),
        runtime_conf=runtime_conf
    )
    _crypto_context = init_crypto_context.execute()

    crypto_provider.set(ctx=_crypto_context)
    return crypto_provider

