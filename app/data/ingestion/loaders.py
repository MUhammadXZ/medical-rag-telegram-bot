from __future__ import annotations

import re
from pathlib import Path

from .models import RawDocument

SUPPORTED_EXTENSIONS = {".txt", ".pdf"}


def load_guideline_documents(path: str | Path) -> list[RawDocument]:
    base_path = Path(path)
    if not base_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {base_path}")

    candidates = (
        [base_path]
        if base_path.is_file()
        else sorted(p for p in base_path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    )

    documents: list[RawDocument] = []
    for file_path in candidates:
        ext = file_path.suffix.lower()
        if ext == ".txt":
            text = file_path.read_text(encoding="utf-8")
        elif ext == ".pdf":
            text = _read_pdf(file_path)
        else:
            continue
        documents.append(
            RawDocument(source=file_path, text=text, year=_extract_year(file_path.stem))
        )
    return documents


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PDF loading requires 'pypdf'. Install it to ingest PDF guideline files."
        ) from exc

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def _extract_year(value: str) -> int | None:
    matches = re.findall(r"(?:19|20)\d{2}", value)
    return int(matches[-1]) if matches else None
