from typing import List, Optional

from src.config import Config


class EventMessageService:

    def __init__(self, conf: Config):
        self.conf = conf

    async def get_event_message_by_page(
        self,
        page: int,
        page_size: Optional[int] = None,
    ) -> List[str]:
        if not page_size:
            page_size = self.conf.different.page_size

        filtered_keys = [
            key for key in self.conf.message_event.all_keys
            if key not in self.conf.message_event.keys_ignore_admin
        ]

        start = (page - 1) * page_size
        end = start + page_size

        return filtered_keys[start:end]
