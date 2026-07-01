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
import zipfile

MAX_CHARS = 20_000
_MAX_DECOMPRESSED = 50 * 1024 * 1024  # 50 MB — reject archives that expand beyond this
_MAX_PDF_PAGES = 500


def _check_zip_bomb(data: bytes) -> None:
    """Reject ZIP-based documents (docx/xlsx/pptx) that would expand beyond the safe limit."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            total = sum(e.file_size for e in zf.infolist())
            if total > _MAX_DECOMPRESSED:
                raise ValueError(
                    f"archive would expand to {total // 1_000_000} MB — rejecting"
                )
    except zipfile.BadZipFile as exc:
        raise ValueError("not a valid ZIP/Office document") from exc


def detect_kind(filename: str, content_type: str = "") -> str:
    name = (filename or "").lower()
    ct = (content_type or "").lower()
    if name.endswith(".pdf") or "pdf" in ct:
        return "pdf"
    if name.endswith((".docx", ".doc")) or "wordprocessingml" in ct or "msword" in ct:
        return "docx"
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
    if kind == "docx":
        return _parse_docx(data)
    if kind == "csv":
        return _parse_csv(data)
    return data.decode("utf-8", errors="replace")[:MAX_CHARS].strip()


def _parse_docx(data: bytes) -> str:
    """Read a .docx (OOXML) into text via python-docx. A legacy binary .doc isn't OOXML and will
    fail here — we say so honestly rather than emit mojibake."""
    try:
        from docx import Document
    except Exception:  # noqa: BLE001 - degrade gracefully if the dep is missing
        return "[docx parsing unavailable — python-docx not installed]"
    try:
        _check_zip_bomb(data)
        doc = Document(io.BytesIO(data))
    except ValueError as exc:
        return f"[rejected: {exc}]"
    except Exception:  # noqa: BLE001 - not a valid .docx (e.g. an old binary .doc)
        return "[could not read the document — save it as .docx, PDF, or text]"
    parts: list[str] = []
    total = 0
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        parts.append(text)
        total += len(text)
        if total > MAX_CHARS:
            break
    return "\n".join(parts).strip()[:MAX_CHARS]


def _parse_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception:  # noqa: BLE001 - degrade gracefully if the dep is missing
        return "[pdf parsing unavailable — pypdf not installed]"
    try:
        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) > _MAX_PDF_PAGES:
            return f"[PDF has {len(reader.pages)} pages — limit is {_MAX_PDF_PAGES}]"
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
    """Fetch a URL and return readable text (markup stripped). Requires network.
    Uses safe_fetch which validates every redirect hop against the SSRF blocklist."""
    from app.tools._ssrf import safe_fetch

    resp = await safe_fetch(url, headers={"User-Agent": "PackBot/1.0"})
    # Clip RAW html first (avoids ReDoS on multi-MB pages), then strip tags.
    return _strip_html(resp.text[: MAX_CHARS * 5])[:MAX_CHARS]
