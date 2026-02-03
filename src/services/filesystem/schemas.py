from pydantic import BaseModel


class EventCreateUiImage(BaseModel):
    ui_image_key: str