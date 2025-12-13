from pydantic import BaseModel


class CurrentPage(BaseModel):
    current_page: int = 1