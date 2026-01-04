from pydantic import BaseModel

class MiscellaneousConf(BaseModel):
    algorithm: str = "HS256"
    dt_format: str = "%Y-%m-%d %H:%M:%S"
    payment_lifetime_seconds: int = 1200 # 20 минут
    fetch_interval: int = 7200  # 2 часа (для обновления курса доллара)
    semaphore_mailing_limit: int = 15
    rate_send_msg_limit: int = 25
    page_size: int = 6
    backup_retention_count: int = 14
