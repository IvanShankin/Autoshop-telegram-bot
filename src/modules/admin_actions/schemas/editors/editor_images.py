from pydantic import BaseModel


class GetNewImageData(BaseModel):
    ui_image_key: str
    current_page: int