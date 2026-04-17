import asyncio
from getpass import getpass
from pathlib import Path
from venv import logger

from src.config import init_env, PathSettings
from src.infrastructure.crypto.secret_storage.client import SecretsStorageClient
from src.infrastructure.crypto.secret_storage.http_secrets_storage import HttpSecretsStorage
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage
from src.tools.init_secrets.bootstrap_service import CryptoBootstrapService
from src.tools.init_secrets.config_dto import EnvInitSecrets
from src.tools.init_secrets.set_secret import SetSecretsUseCase


async def main():
    # грузим отдельный env для секретов
    paths = PathSettings.build(use_secret_storage=True)
    init_env(str(paths.base_dir / Path(".secrets.env")))

    try:
        conf = EnvInitSecrets.from_env()
    except KeyError:
        logger.exception("'.secrets.env' не заполнен!")
        return

    secret_client = SecretsStorageClient(
        base_url=conf.storage_server_url,
        cert=(
            str(paths.ssl_client_cert_file),
            str(paths.ssl_client_key_file),
        ),
        ca=str(paths.ssl_ca_file),
    )

    storage: SecretsStorage = HttpSecretsStorage(secret_client)

    passphrase = getpass("Enter master passphrase: ")

    crypto_service = CryptoBootstrapService(storage)
    crypto = crypto_service.init_dek(passphrase)

    use_case = SetSecretsUseCase(storage, crypto)
    use_case.execute()


if __name__ == "__main__":
    asyncio.run(main())