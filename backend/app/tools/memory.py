"""Local-only pack memory (v2) — what the pack learned across hunts, no accounts.

The Elder reads recent entries to seed planning (so the next hunt starts smarter) and writes one
durable takeaway when a hunt finishes. It lives in the device's Postgres `memory` table; this
module is the thin facade the Supervisor uses. Memory must NEVER break a hunt — every call is
best-effort and degrades to "no memory" on any error.
"""

from __future__ import annotations

import re
from typing import Protocol

_CAP = 3  # at most this many past notes injected — keep the context lean


class MemoryStore(Protocol):
    async def recent_memory(self, limit: int = 5) -> list[dict]: ...
    async def save_memory(self, hunt_id: str | None, kind: str, text: str) -> None: ...


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(w) > 2}


def _relevant(notes: list[str], task: str) -> list[str]:
    """Keep only past notes that share keywords with THIS task — global recency would pollute every
    hunt with unrelated lessons (and burn tokens). No topic signal → nothing (not noise)."""
    task_words = _words(task)
    if not task_words:
        return []
    matched = [n for n in notes if task_words & _words(n)]
    return matched[:_CAP]


async def recall(repo: MemoryStore, task: str = "", limit: int = 12) -> str:
    """A short note of what the pack learned on PAST hunts ABOUT THIS topic, to seed planning. Empty
    on a first hunt or when nothing past is relevant."""
    try:
        rows = await repo.recent_memory(limit)
    except Exception:  # noqa: BLE001 — memory is best-effort; never sink a hunt
        return ""
    notes = [str(r.get("text") or "").strip() for r in rows if str(r.get("text") or "").strip()]
    notes = _relevant(notes, task)
    if not notes:
        return ""
    return "What the pack learned on past hunts (use it if relevant):\n- " + "\n- ".join(notes)


async def remember(repo: MemoryStore, hunt_id: str, text: str) -> None:
    """Write one takeaway from this hunt for next time (best-effort)."""
    text = (text or "").strip()
    if not text:
        return
    try:
        await repo.save_memory(hunt_id, "takeaway", text)
    except Exception:  # noqa: BLE001
        pass
