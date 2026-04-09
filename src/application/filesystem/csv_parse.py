import csv
import io
from pathlib import Path
from typing import Callable


def _parse_csv(fun_get_text: Callable[[str], str]) -> csv.DictReader:
    for enc in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            text = fun_get_text(enc)
            return parse_csv_text(text)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "csv",
        b"",
        0,
        1,
        "Не удалось определить кодировку CSV"
    )


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


def parse_csv_from_bytes(stream: io.BytesIO) -> csv.DictReader:
    return _parse_csv(lambda encoding: stream.read().decode(encoding))


def parse_csv_from_file(path: Path) -> csv.DictReader:
    return _parse_csv(lambda encoding: path.read_text(encoding=encoding))
