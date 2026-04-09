from dataclasses import dataclass
from enum import Enum


class RuntimeMode(str, Enum):
    DEV = "DEV"
    TEST = "TEST"
    PROD = "PROD"


@dataclass(frozen=True)
class SecretsRuntime:
    mode: RuntimeMode
    storage_url: str
    cert: tuple[str, str]
    ca: str


_runtime: SecretsRuntime | None = None


def set_runtime(runtime: SecretsRuntime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> SecretsRuntime:
    if _runtime is None:
        raise RuntimeError("Secrets runtime is not initialized")
    return _runtime
