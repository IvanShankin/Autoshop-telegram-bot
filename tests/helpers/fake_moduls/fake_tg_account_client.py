from datetime import datetime
from typing import List, Tuple, Any


class FakeTelegramAccountClient:

    def __init__(
        self,
        result_validate: Any = True,
        result_get_auth_codes: List[Tuple[datetime, str]] = None,
    ):
        self.result_validate = result_validate
        self.result_get_auth_codes = result_get_auth_codes if result_get_auth_codes else [(datetime.now(), "12345")]

    async def validate(self, *args, **kwargs):
        return self.result_validate

    async def get_auth_codes(self, *args, **kwargs):
        return self.result_get_auth_codes
