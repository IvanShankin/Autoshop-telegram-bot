import os


class FileStorage:
    def exists(self, file_path: str) -> bool:
        return True if os.path.exists(file_path) else False