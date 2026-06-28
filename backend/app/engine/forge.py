"""The Forge (v2) — turns Howler's tagged blocks into real, downloadable files.

Pure rendering, NO model calls: it takes the brief (a title + prose blocks) and renders Markdown,
HTML, PDF, and DOCX. Each comes back as bytes the Supervisor saves as an artifact. Documents-first
per the v2 plan; broader formats (XLSX/PPTX/PNG) come later. Every renderer is best-effort — a
failure in one format never sinks the others.
"""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

import markdown as _markdown
from docx import Document
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# format -> MIME type for downloads.
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME: dict[str, str] = {
    "md": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "pdf": "application/pdf",
    "docx": _DOCX_MIME,
}


def _title_and_paras(blocks: list[dict], title: str = "") -> tuple[str, list[str]]:
    """Split blocks into a title + body paragraphs. A leading '# Heading' becomes the title."""
    paras: list[str] = []
    for b in blocks:
        text = str(b.get("text") or "").strip()
        if not text:
            continue
        if not title and text.startswith("# "):
            title = text.lstrip("# ").strip()
            continue
        paras.append(text.lstrip("# ").strip() if text.startswith("# ") else text)
    return (title or "The Pack's brief"), paras


def _render_markdown(title: str, paras: list[str]) -> bytes:
    return (f"# {title}\n\n" + "\n\n".join(paras)).encode("utf-8")


def _render_html(title: str, paras: list[str]) -> bytes:
    body = _markdown.markdown("\n\n".join(paras))
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title>"
        "<style>body{font:16px/1.6 -apple-system,Segoe UI,sans-serif;max-width:720px;"
        "margin:40px auto;padding:0 16px;color:#1a1a1a}h1{font-size:28px}</style></head>"
        f"<body><h1>{escape(title)}</h1>{body}</body></html>"
    )
    return html.encode("utf-8")


def _render_pdf(title: str, paras: list[str]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, title=title)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 14)]
    for p in paras:
        story.append(Paragraph(escape(p), styles["BodyText"]))
        story.append(Spacer(1, 8))
    doc.build(story)
    return buf.getvalue()


def _render_docx(title: str, paras: list[str]) -> bytes:
    d = Document()
    d.add_heading(title, level=0)
    for p in paras:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


_RENDERERS = {
    "md": _render_markdown,
    "html": _render_html,
    "pdf": _render_pdf,
    "docx": _render_docx,
}


def forge(
    blocks: list[dict], title: str = "", formats: list[str] | None = None
) -> dict[str, bytes]:
    """Render the brief's blocks to the requested document formats. Returns {format: bytes}. A
    renderer that raises is skipped (best-effort) rather than sinking the whole Forge."""
    title, paras = _title_and_paras(blocks, title)
    out: dict[str, bytes] = {}
    for fmt in formats or list(_RENDERERS):
        renderer = _RENDERERS.get(fmt)
        if renderer is None:
            continue
        try:
            out[fmt] = renderer(title, paras)
        except Exception:  # noqa: BLE001 — one bad format never sinks the rest
            continue
    return out
