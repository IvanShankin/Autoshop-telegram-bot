import csv
import io
from pathlib import Path


def parse_csv_text(text: str) -> csv.DictReader:
    """
    Универсальный парсер CSV:
    - убирает BOM
    - автоматически определяет delimiter
    """
    text = text.lstrip("\ufeff")

    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(text)

    return csv.DictReader(io.StringIO(text), dialect=dialect)


def parse_csv_from_bytes(stream: io.BytesIO, encoding: str = "utf-8") -> csv.DictReader:
    text = stream.read().decode(encoding)
    return parse_csv_text(text)


def parse_csv_from_file(path: Path, encoding: str = "utf-8") -> csv.DictReader:
    text = path.read_text(encoding=encoding)
    return parse_csv_text(text)
