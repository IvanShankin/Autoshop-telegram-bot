from pydantic import BaseModel


class FileLimits(BaseModel):
    max_size_mb: int = 10
    max_size_bytes: int = 10 * 1024 * 1024      # 10 мегабайт = 10 * 1024 * 1024
    max_download_size: int = 20 * 1024 * 1024   # 20 MB
    max_upload_file: int = 49 * 1024 * 1024    # 49 MB (с запасом)
