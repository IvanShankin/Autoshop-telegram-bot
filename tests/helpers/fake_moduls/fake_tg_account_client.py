from datetime import datetime
from typing import List, Tuple


class FakeTelegramAccountClient:

    def __init__(
        self,
        result_validate: bool = True,
        result_get_auth_codes: List[Tuple[datetime, str]] = None,
    ):
        self.result_validate = result_validate
        self.result_get_auth_codes = result_get_auth_codes if result_get_auth_codes else [(datetime.now(), "12345")]

    def validate(self, *args, **kwargs):
        return self.result_validate

    def get_auth_codes(self, *args, **kwargs):
        return self.result_get_auth_codes
