"""file_parse — DOCX now reads to real text (C1 fix), not utf-8 mojibake."""

from __future__ import annotations

import io

from app.tools.file_parse import detect_kind, parse_bytes


def _make_docx(paragraphs: list[str]) -> bytes:
    from docx import Document

    d = Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_detect_kind_recognizes_docx() -> None:
    assert detect_kind("notes.docx", "") == "docx"
    ooxml = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert detect_kind("x", ooxml) == "docx"


def test_docx_parses_to_real_text() -> None:
    data = _make_docx(["The solid-state battery roadmap.", "Supplier costs and the risk table."])
    text = parse_bytes(data, "docx")
    assert "solid-state battery roadmap" in text
    assert "Supplier costs" in text
    # The bug we fixed: a real .docx must NOT come back as binary/zip mojibake.
    assert "PK" not in text[:4]


def test_non_docx_bytes_degrade_honestly() -> None:
    # Random bytes labelled docx → an honest notice, never garbage prose.
    out = parse_bytes(b"\x00\x01not a real docx\xff", "docx")
    assert out.startswith("[could not read the document")
