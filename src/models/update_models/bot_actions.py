from pathlib import Path
from typing import Optional, Any

from pydantic import BaseModel


class EditMessagePhoto(BaseModel):
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    file_path: Optional[str | Path] = None
    file_id: Optional[str] = None
    reply_markup: Any = None,
