"""Local-only pack memory (v2) — what the pack learned across hunts, no accounts.

The Elder reads recent entries to seed planning (so the next hunt starts smarter) and writes one
durable takeaway when a hunt finishes. It lives in the device's Postgres `memory` table; this
module is the thin facade the Supervisor uses. Memory must NEVER break a hunt — every call is
best-effort and degrades to "no memory" on any error.
"""

from __future__ import annotations

from typing import Protocol


class MemoryStore(Protocol):
    async def recent_memory(self, limit: int = 5) -> list[dict]: ...
    async def save_memory(self, hunt_id: str | None, kind: str, text: str) -> None: ...


async def recall(repo: MemoryStore, limit: int = 5) -> str:
    """A short note of what the pack learned before, to seed planning. Empty on a first hunt."""
    try:
        rows = await repo.recent_memory(limit)
    except Exception:  # noqa: BLE001 — memory is best-effort; never sink a hunt
        return ""
    notes = [str(r.get("text") or "").strip() for r in rows if str(r.get("text") or "").strip()]
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
