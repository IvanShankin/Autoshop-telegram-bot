

# ALGORITHM = "HS256"
#
# DT_FORMAT = "%Y-%m-%d %H:%M:%S"
# PAYMENT_LIFETIME_SECONDS = 1200 # 20 минут
# FETCH_INTERVAL = 7200 # 2 часа (для обновления курса доллара)
#
# SEMAPHORE_MAILING_LIMIT = 15
# RATE_SEND_MSG_LIMIT = 25
#
# PAGE_SIZE = 6

from pydantic import BaseModel

class MiscellaneousConf(BaseModel):
    algorithm: str = "HS256"
    dt_format: str = "%Y-%m-%d %H:%M:%S"
    payment_lifetime_seconds: int = 1200 # 20 минут
    fetch_interval: int = 7200  # 2 часа (для обновления курса доллара)
    semaphore_mailing_limit: int = 15
    rate_send_msg_limit: int = 25
    page_size: int =6
