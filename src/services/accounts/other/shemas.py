from pydantic import BaseModel


class ImportResult(BaseModel):
    successfully_added: int
    total_processed: int
    errors_csv_bytes: bytes | None
    duplicates_csv_bytes: bytes | None

class AccountImportData(BaseModel):
    phone: str | None
    login: str | None
    password: str | None