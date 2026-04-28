import os
from pathlib import Path

from pydantic import BaseModel


class EnvInitSecrets(BaseModel):
    storage_server_url: str
    cert_dir: Path

    @classmethod
    def from_env(cls):
        return cls(
            storage_server_url=os.environ["STORAGE_SERVER_URL"],
            cert_dir=Path(os.environ["CERT_DIR"]),
        )
