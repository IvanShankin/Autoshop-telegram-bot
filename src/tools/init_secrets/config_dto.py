import os

from pydantic import BaseModel


class EnvInitSecrets(BaseModel):
    storage_server_url: str

    @classmethod
    def from_env(cls):
        return cls(
            storage_server_url=os.environ["STORAGE_SERVER_URL"],
        )
