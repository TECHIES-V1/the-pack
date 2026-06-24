"""File/document parsing — turn an uploaded file or URL into plain text the pack can research.

INLINE, no object store: the file's CONTENT is what matters for research, so we extract text
and feed it into the hunt as context. Text/CSV/Markdown decode directly; PDF via pypdf; a URL
is fetched and lightly stripped of markup. Mirrors the SearchProvider/Transcriber seam — swap
a body, nothing upstream changes.
"""

from __future__ import annotations

import csv as _csv
import io
import re

MAX_CHARS = 20_000


def detect_kind(filename: str, content_type: str = "") -> str:
    name = (filename or "").lower()
    ct = (content_type or "").lower()
    if name.endswith(".pdf") or "pdf" in ct:
        return "pdf"
    if name.endswith(".csv") or "csv" in ct:
        return "csv"
    if name.endswith((".md", ".markdown")):
        return "md"
    if ct.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
        return "image"
    if ct.startswith("video/") or name.endswith((".mp4", ".mov", ".webm", ".avi", ".mkv")):
        return "video"
    return "text"


def parse_bytes(data: bytes, kind: str) -> str:
    """Extract plain text from raw bytes by kind. Never raises — returns a note on failure."""
    if kind == "pdf":
        return _parse_pdf(data)
    if kind == "csv":
        return _parse_csv(data)
    return data.decode("utf-8", errors="replace")[:MAX_CHARS].strip()


def _parse_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception:  # noqa: BLE001 - degrade gracefully if the dep is missing
        return "[pdf parsing unavailable — pypdf not installed]"
    try:
        reader = PdfReader(io.BytesIO(data))
        out: list[str] = []
        total = 0
        for page in reader.pages:
            chunk = page.extract_text() or ""
            out.append(chunk)
            total += len(chunk)
            if total > MAX_CHARS:
                break
        return "\n".join(out).strip()[:MAX_CHARS]
    except Exception as exc:  # noqa: BLE001
        return f"[could not read the PDF: {exc}]"


def _parse_csv(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    rows = list(_csv.reader(io.StringIO(text)))
    lines = [" | ".join(cell for cell in row) for row in rows[:200]]
    return "\n".join(lines)[:MAX_CHARS]


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


async def parse_url(url: str) -> str:
    """Fetch a URL and return readable text (markup stripped). Requires network."""
    import httpx

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "PackBot/1.0"})
        resp.raise_for_status()
        return _strip_html(resp.text)[:MAX_CHARS]
