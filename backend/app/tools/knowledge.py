"""Local knowledge base (v4.2) — your own documents, woven into a hunt's research.

Uploaded files are parsed to text and stored (the `documents` table). When a hunt runs, the most
relevant docs are selected by simple keyword overlap with the task and injected as SOURCES — each
with a synthetic `lib://<id>` url so the source de-dupe (which keys on url) keeps them, and
`by="your library", verified=True` so they read as first-class, traceable ground in the brief.

Deterministic (no model call) so the offline path stays green. Best-effort: never sink a hunt.
"""

from __future__ import annotations

import re

_MAX_DOCS = 3
_PER_DOC = 1200  # chars of a doc injected
_BUDGET = 3000  # total chars across all injected docs (keeps context bounded)


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(w) > 2}


def select_relevant(docs: list[dict], task: str) -> list[dict]:
    """Pick the docs sharing keywords with the task; return them as injectable source dicts."""
    task_words = _words(task)
    if not task_words:
        return []
    scored: list[tuple[int, dict]] = []
    for d in docs:
        overlap = len(task_words & _words(str(d.get("text") or "")))
        if overlap:
            scored.append((overlap, d))
    scored.sort(key=lambda t: t[0], reverse=True)

    out: list[dict] = []
    used = 0
    for _score, d in scored[:_MAX_DOCS]:
        excerpt = str(d.get("text") or "")[:_PER_DOC]
        if used + len(excerpt) > _BUDGET:
            excerpt = excerpt[: max(0, _BUDGET - used)]
        if not excerpt:
            break
        used += len(excerpt)
        out.append(
            {
                "title": str(d.get("name") or "document"),
                "url": f"lib://{d.get('id')}",  # synthetic, stable — survives source de-dupe
                "snippet": excerpt[:400],
                "text": excerpt,
                "by": "your library",
                "verified": True,
            }
        )
    return out
