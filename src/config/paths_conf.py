# BASE_DIR = Path(__file__).resolve().parent.parent.parent
# sys.path.append(str(BASE_DIR))
# LOCALES_DIR = BASE_DIR / 'locales'
# MEDIA_DIR = BASE_DIR / "media"
# LOG_DIR = MEDIA_DIR / 'logs'
# LOG_FILE = LOG_DIR / "auto_shop_bot.log"
# ACCOUNTS_DIR = MEDIA_DIR / "accounts"
# TEMP_FILE_DIR = MEDIA_DIR / "temp"
# SENT_MASS_MSG_IMAGE_DIR = MEDIA_DIR / "sent_mass_msg_image"
#
# # сертификаты
# CERT_DIR = BASE_DIR / "certs"
# SSL_CLIENT_CERT_FILE = CERT_DIR / "client" / "client_cert.pem"
# SSL_CLIENT_KEY_FILE = CERT_DIR / "client" / "client_key.pem"
# SSL_CA_FILE = CERT_DIR / "ca" / "client_ca_chain.pem"

from pathlib import Path
from pydantic import BaseModel


class PathSettings(BaseModel):
    base_dir: Path
    locales_dir: Path
    media_dir: Path
    log_dir: Path
    log_file: Path
    accounts_dir: Path
    temp_file_dir: Path
    sent_mass_msg_image_dir: Path
    ui_sections_dir: Path

    # сертификаты
    cert_dir: Path
    ssl_client_cert_file: Path
    ssl_client_key_file: Path
    ssl_ca_file: Path


    @classmethod
    def build(cls) -> "PathSettings":
        base = Path(__file__).resolve().parents[2]
        media = base / "media"
        cert_dir = base / "certs"

        return cls(
            base_dir=base,
            locales_dir=base / "locales",
            media_dir=media,
            log_dir=media / "logs",
            log_file=media / "logs" / "auto_shop_bot.log",
            accounts_dir=media / "accounts",
            temp_file_dir=media / "temp",
            sent_mass_msg_image_dir=media / "sent_mass_msg_image",
            ui_sections_dir=media  / "ui_sections",

            cert_dir=cert_dir,
            ssl_client_cert_file=cert_dir / "client" / "client_cert.pem",
            ssl_client_key_file=cert_dir / "client" / "client_key.pem",
            ssl_ca_file=cert_dir / "ca" / "client_ca_chain.pem",
        )
