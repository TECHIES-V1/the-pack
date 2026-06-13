"""The event bus — Redis Streams, one stream per hunt.

The Python engine is the ONLY writer: it appends every event with XADD. The Rust gateway
is a read-only consumer (XRANGE for replay, XREAD for the live tail) and never touches
this writer. One JSON envelope format end to end — no second format (Doc 04 §2).
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis

from app.events.models import Event


def stream_key(hunt_id: str) -> str:
    return f"hunt:{hunt_id}:events"


class EventBus:
    """Append-only writer over Redis Streams. seq is owned by the engine, not Redis."""

    def __init__(self, url: str) -> None:
        self._redis = redis.from_url(url, decode_responses=True)

    async def append(self, event: Event) -> str:
        """XADD one envelope. Returns the Redis stream id (not our seq)."""
        return await self._redis.xadd(
            stream_key(event.hunt_id),
            {"event": event.to_json()},
        )

    async def replay(self, hunt_id: str, from_seq: int = 0) -> list[dict[str, Any]]:
        """XRANGE the whole stream, filtered to seq >= from_seq. Used for gap replay."""
        import json

        entries = await self._redis.xrange(stream_key(hunt_id))
        out: list[dict[str, Any]] = []
        for _id, fields in entries:
            ev = json.loads(fields["event"])
            if ev.get("seq", 0) >= from_seq:
                out.append(ev)
        return out

    async def close(self) -> None:
        await self._redis.aclose()
