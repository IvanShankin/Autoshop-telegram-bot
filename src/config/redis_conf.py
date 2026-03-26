from datetime import timedelta

from pydantic import BaseModel


class RedisTimeStorage(BaseModel):
    user: timedelta
    subscription_prompt: timedelta
    sold_accounts_by_owner: timedelta
    sold_account_by_account: timedelta
    sold_universal_account_product_by_owner: timedelta
    sold_universal_product_by_product: timedelta
    all_voucher: timedelta

    @classmethod
    def build(cls) -> "RedisTimeStorage":
        return cls(
            user=timedelta(hours=6),
            subscription_prompt = timedelta(days=15),
            sold_accounts_by_owner = timedelta(hours=6),
            sold_account_by_account = timedelta(hours=6),
            sold_universal_account_product_by_owner = timedelta(hours=6),
            sold_universal_product_by_product = timedelta(hours=6),
            all_voucher = timedelta(hours=10)
        )
