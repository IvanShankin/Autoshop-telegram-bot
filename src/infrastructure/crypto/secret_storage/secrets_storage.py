from typing import Protocol
from pathlib import Path


class SecretsStorage(Protocol):
    # --- health ---
    def health(self) -> None: ...

    # --- strings ---
    def get_secret(self, name: str, version: int | None = None) -> dict: ...

    def create_secret(
        self,
        name: str,
        encrypted_data: str,
        nonce: str,
        sha256: str,
    ) -> None: ...

    def create_secret_version(
        self,
        name: str,
        encrypted_data: str,
        nonce: str,
        sha256: str,
    ) -> None: ...

    # --- files ---
    def get_secret_file_meta(self, name: str, version: int | None = None) -> dict: ...

    def upload_secret_file(
        self,
        name: str,
        file_path: Path,
        nonce_b64: str,
        sha256_b64: str,
    ) -> None: ...

    def upload_secret_file_version(
        self,
        name: str,
        file_path: Path,
        nonce_b64: str,
        sha256_b64: str,
    ) -> None: ...

    def download_secret_file(
        self,
        name: str,
        dst_path: Path,
        version: int | None = None,
    ) -> None: ...

    # --- delete ---
    def purge_secret(self, name: str) -> None: ...