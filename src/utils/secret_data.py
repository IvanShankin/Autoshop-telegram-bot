import base64

from cryptography.fernet import Fernet
from src.config import SECRET_KEY

key = base64.urlsafe_b64encode(SECRET_KEY.encode().ljust(32, b'0')[:32])
fernet = Fernet(key)

def encrypt_token(text: str) -> str:
    """Шифрует переданный текст"""
    return fernet.encrypt(text.encode()).decode()

def decrypt_token(text_encrypted: str) -> str:
    """Расшифровывает переданный зашифрованный текст"""
    return fernet.decrypt(text_encrypted.encode()).decode()