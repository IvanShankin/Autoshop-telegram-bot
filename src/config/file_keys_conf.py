from pathlib import Path

from pydantic import BaseModel


class FilePathAndKey(BaseModel):
    key: str
    path: Path
    name_in_dir_with_files: str


class FileKeysConf(BaseModel):
    example_zip_for_universal_import_key: FilePathAndKey
    example_zip_for_import_tg_acc_key: FilePathAndKey
    example_csv_for_import_other_acc_key: FilePathAndKey

