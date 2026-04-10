from dataclasses import dataclass


@dataclass
class CryptoContext:
    kek: bytes
    dek: bytes
    nonce_b64_dek: str