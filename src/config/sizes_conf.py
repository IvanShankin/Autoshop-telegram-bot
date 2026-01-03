# MAX_SIZE_MB = 10
# MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024  # 10 мегабайт = 10 * 1024 * 1024
# MAX_DOWNLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
# MAX_UPLOAD_FILE = 49 * 1024 * 1024  # 49 MB (с запасом)

from pydantic import BaseModel


class FileLimits(BaseModel):
    max_size_mb: int = 10
    max_size_bytes: int = 10 * 1024 * 1024      # 10 мегабайт = 10 * 1024 * 1024
    max_download_size: int = 20 * 1024 * 1024   # 20 MB
    max_upload_file: int = 49 * 1024 * 1024    # 49 MB (с запасом)
