import hashlib
import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def unwrap_dek(
    encrypted_data_b64: str,
    nonce_b64: str,
    kek: bytes,
) -> bytes:
    ciphertext = base64.b64decode(encrypted_data_b64)
    nonce = base64.b64decode(nonce_b64)

    aesgcm = AESGCM(kek)
    return aesgcm.decrypt(nonce, ciphertext, None)


def encrypt_text(plaintext: str, dek: bytes, nonce_b64:  bytes = None) -> tuple[str, str, str]:
    """
    Возвращает:
    encrypted_data_b64, nonce_b64, sha256_b64
    """
    data = plaintext.encode("utf-8")

    if not nonce_b64:
        nonce_b64 = os.urandom(12)

    aesgcm = AESGCM(dek)

    ciphertext = aesgcm.encrypt(nonce_b64, data, None)

    sha256 = hashlib.sha256(ciphertext).digest()

    return (
        base64.b64encode(ciphertext).decode("ascii"),
        base64.b64encode(nonce_b64).decode("ascii"),
        base64.b64encode(sha256).decode("ascii"),
    )
