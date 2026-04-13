from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel

from src.config import Config


def get_import_universal_headers(conf: Config) -> List[str]:
    import_universal_headers = ["filename"]
    for lang in conf.app.allowed_langs:
        import_universal_headers.append("description_" + lang)

    return import_universal_headers


class UniversalProductsParse(BaseModel):
    file_name: Optional[str]
    descriptions: Dict[str, str] # Dict[код языка, описание]


@dataclass(slots=True)
class PreparedUniversalProduct:
    storage_uuid: Optional[str]
    file_path: Optional[str]
    original_filename: Optional[str]
    checksum: Optional[str]
    encrypted_key_b64: str
    encrypted_key_nonce: str
    encrypted_descriptions: Dict[str, Tuple[str, str]]


class UploadUniversalProduct(BaseModel):
    file_name: str
    descriptions: Dict[str, str] # Dict[код языка, описание]
