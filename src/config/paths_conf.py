import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
LOCALES_DIR = BASE_DIR / 'locales'
MEDIA_DIR = BASE_DIR / "media"
LOG_DIR = MEDIA_DIR / 'logs'
LOG_FILE = LOG_DIR / "auto_shop_bot.log"
ACCOUNTS_DIR = MEDIA_DIR / "accounts"
TEMP_FILE_DIR = MEDIA_DIR / "temp"
SENT_MASS_MSG_IMAGE_DIR = MEDIA_DIR / "sent_mass_msg_image"

# сертификаты
CERT_DIR = BASE_DIR / "certs"
SSL_CLIENT_CERT_FILE = CERT_DIR / "client" / "client_cert.pem"
SSL_CLIENT_KEY_FILE = CERT_DIR / "client" / "client_key.pem"
SSL_CA_FILE = CERT_DIR / "ca" / "client_ca_chain.pem"