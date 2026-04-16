from src.config.secrets_conf import SecretSettings
from src.domain.crypto.key_ops import encrypt_text
from src.domain.crypto.models import CryptoContext
from src.exceptions import StorageNotFound, StorageConflict
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage
from src.tools.init_secrets.helper import read_secret


class SetSecretsUseCase:

    def __init__(self, storage: SecretsStorage, crypto: CryptoContext):
        self.storage = storage
        self.crypto = crypto

    def execute(self):
        for secret_name in SecretSettings.model_fields.keys():
            try:
                # проверяем существует ли секрет
                self.storage.get_secret(secret_name)

                # спрашиваем overwrite
                while True:
                    answer = input(
                        f"Secret '{secret_name}' exists. Overwrite? (y/n): "
                    ).strip().lower()

                    if answer in {"y", "n"}:
                        break

                    print("Please enter 'y' or 'n'")

                if answer == "n":
                    print(f"Skipped: {secret_name}")
                    continue

                # обновление версии
                encrypted_data, nonce, sha256 = self._encrypt(secret_name)

                self.storage.create_secret_version(
                    name=secret_name,
                    encrypted_data=encrypted_data,
                    nonce=nonce,
                    sha256=sha256,
                )

                print(f"Updated: {secret_name}")

            except StorageNotFound:
                # создаём новый секрет
                encrypted_data, nonce, sha256 = self._encrypt(secret_name)

                try:
                    self.storage.create_secret(
                        name=secret_name,
                        encrypted_data=encrypted_data,
                        nonce=nonce,
                        sha256=sha256,
                    )

                    print(f"Created: {secret_name}")

                except StorageConflict:
                    # секрет "удалён" (soft delete)
                    print(f"Purging deleted secret: {secret_name}")

                    self.storage.purge_secret(secret_name)

                    self.storage.create_secret(
                        name=secret_name,
                        encrypted_data=encrypted_data,
                        nonce=nonce,
                        sha256=sha256,
                    )

                    print(f"Re-created: {secret_name}")

            except Exception as e:
                print(f"[ERROR] {secret_name}: {e}")

    def _encrypt(self, secret_name: str) -> tuple[str, str, str]:
        secret_value = read_secret(secret_name)
        return encrypt_text(secret_value, self.crypto.dek)