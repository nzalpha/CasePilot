from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import fitz


class ExtractedPage(TypedDict):
    page_number: int
    text: str


def extract_pdf_pages(file_path: str | Path) -> list[ExtractedPage]:
    pages: list[ExtractedPage] = []
    document = fitz.open(file_path)
    try:
        for index, page in enumerate(document):
            text = page.get_text("text").strip()
            pages.append({"page_number": index + 1, "text": text})
    finally:
        document.close()
    return pages
