from __future__ import annotations

import re

from .models import Section

HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
ALL_CAPS_RE = re.compile(r"^[A-Z][A-Z\s\-]{4,}$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(text: str, default_title: str = "General") -> list[Section]:
    lines = [line.strip() for line in text.split("\n")]
    sections: list[Section] = []

    current_title = default_title
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines:
            sections.append(Section(title=current_title, text="\n".join(current_lines).strip()))

    for line in lines:
        if not line:
            current_lines.append("")
            continue

        if _is_heading(line):
            flush()
            current_title = line
            current_lines = []
        else:
            current_lines.append(line)

    flush()
    return [section for section in sections if section.text]


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    sentences = SENTENCE_SPLIT_RE.split(normalized)
    return [s.strip() for s in sentences if s.strip()]


def token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def _is_heading(line: str) -> bool:
    if len(line) > 120:
        return False
    if HEADING_RE.match(line):
        return True
    return bool(ALL_CAPS_RE.match(line))
