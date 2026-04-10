from pathlib import Path

from src.infrastructure.crypto.secret_storage.client import SecretsStorageClient
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage


class HttpSecretsStorage(SecretsStorage):
    def __init__(self, client: SecretsStorageClient):
        self._client = client

    # --- health ---
    def health(self) -> None:
        self._client.health()

    # --- strings ---
    def get_secret(self, name: str, version: int | None = None) -> dict:
        return self._client.get_secret_string(name=name, version=version)

    def create_secret(
        self,
        name: str,
        encrypted_data: str,
        nonce: str,
        sha256: str,
    ) -> None:
        self._client.create_secret_string(
            name=name,
            encrypted_data=encrypted_data,
            nonce=nonce,
            sha256=sha256,
        )

    def create_secret_version(
        self,
        name: str,
        encrypted_data: str,
        nonce: str,
        sha256: str,
    ) -> None:
        self._client.create_next_string_version(
            name=name,
            encrypted_data=encrypted_data,
            nonce=nonce,
            sha256=sha256,
        )

    # --- files ---
    def get_secret_file_meta(self, name: str, version: int | None = None) -> dict:
        return self._client.get_secret_file_meta(name=name, version=version)

    def upload_secret_file(
        self,
        name: str,
        file_path: Path,
        nonce_b64: str,
        sha256_b64: str,
    ) -> None:
        self._client.upload_secret_file(
            name=name,
            file_path=file_path,
            nonce_b64=nonce_b64,
            sha256_b64=sha256_b64,
        )

    def upload_secret_file_version(
        self,
        name: str,
        file_path: Path,
        nonce_b64: str,
        sha256_b64: str,
    ) -> None:
        self._client.upload_next_file_version(
            name=name,
            file_path=file_path,
            nonce_b64=nonce_b64,
            sha256_b64=sha256_b64,
        )

    def download_secret_file(
        self,
        name: str,
        dst_path: Path,
        version: int | None = None,
    ) -> None:
        self._client.download_secret_file(
            name=name,
            dst_path=dst_path,
            version=version,
        )

    # --- delete ---
    def purge_secret(self, name: str) -> None:
        self._client.purge_secret(name=name)