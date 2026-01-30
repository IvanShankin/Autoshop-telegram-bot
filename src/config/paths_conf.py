import os.path
from pathlib import Path
from pydantic import BaseModel


class PathSettings(BaseModel):
    base_dir: Path

    locales_dir: Path
    media_dir: Path

    log_dir: Path
    log_file: Path

    files_dir: Path

    products_dir: Path
    accounts_dir: Path
    universals_dir: Path

    temp_dir: Path
    sent_mass_msg_image_dir: Path
    ui_sections_dir: Path

    # сертификаты
    cert_dir: Path
    ssl_client_cert_file: Path
    ssl_client_key_file: Path
    ssl_ca_file: Path

    @classmethod
    def build(cls, mode: str) -> "PathSettings":
        base = Path(__file__).resolve().parents[2]
        media = base / Path("media")
        products = media / Path("products")
        cert_dir = base / Path("certs")
        files_dir = media / Path("files")

        os.makedirs(media, exist_ok=True)
        os.makedirs(products, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        os.makedirs(cert_dir, exist_ok=True)

        ssl_client_cert_file = cert_dir / Path("client") / Path("client_cert.pem")
        ssl_client_key_file = cert_dir / Path("client") / Path("client_key.pem")
        ssl_ca_file = cert_dir / Path("ca") / Path("client_ca_chain.pem")

        if (
            not mode in {"DEV", "TEST"} and
            (
                not os.path.isfile(str(ssl_client_cert_file)) or
                not os.path.isfile(str(ssl_client_key_file)) or
                not os.path.isfile(str(ssl_ca_file))
            )
        ):
            raise FileNotFoundError("Certs not fount")

        return cls(
            base_dir=base,
            locales_dir=base / Path("locales"),
            media_dir=media,
            log_dir=media / Path("logs"),
            log_file=media / Path("logs") / Path("auto_shop_bot.log"),
            files_dir=files_dir,
            products_dir=products,
            accounts_dir=products / Path("accounts"),
            universals_dir=products / Path("universals"),
            temp_dir=media / Path("temp"),
            sent_mass_msg_image_dir=media / Path("sent_mass_msg_image"),
            ui_sections_dir=media  / Path("ui_sections"),

            cert_dir=cert_dir,
            ssl_client_cert_file=ssl_client_cert_file,
            ssl_client_key_file=ssl_client_key_file,
            ssl_ca_file=ssl_ca_file,
        )
