"""The repository — every Postgres read and write the engine needs (Doc 04 §5).

This is the only module that speaks SQL. The Emitter (app/engine/core.py) calls
`append_event`; the outbox relay (app/engine/relay.py) calls `fetch_unrelayed` +
`mark_relayed`; the REST layer calls the hunt/instinct/artifact helpers.

`append_event` writes the event AND fires `pg_notify('pack_events', hunt_id)` in the SAME
transaction. The notify reaches the relay only on commit, so the relay is woken precisely
when there is a durably-committed event to publish — the heart of the outbox pattern.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from app.events.models import Event

NOTIFY_CHANNEL = "pack_events"


class Repo:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- hunts -------------------------------------------------------------------------

    async def create_hunt(self, hunt_id: str, source: str, raw_input: str | None) -> None:
        await self._pool.execute(
            """
            INSERT INTO hunts (hunt_id, state, source, raw_input)
            VALUES ($1, 'planning', $2, $3)
            ON CONFLICT (hunt_id) DO NOTHING
            """,
            hunt_id,
            source,
            raw_input,
        )

    async def set_hunt_state(self, hunt_id: str, state: str) -> None:
        await self._pool.execute(
            "UPDATE hunts SET state = $2, updated_at = now() WHERE hunt_id = $1",
            hunt_id,
            state,
        )

    async def set_boundary(self, hunt_id: str, boundary_usd: float) -> None:
        await self._pool.execute(
            "UPDATE hunts SET boundary_usd = $2, updated_at = now() WHERE hunt_id = $1",
            hunt_id,
            boundary_usd,
        )

    async def get_hunt_snapshot(self, hunt_id: str) -> dict[str, Any] | None:
        """State + last_seq, or None if the hunt does not exist (REST returns 404)."""
        row = await self._pool.fetchrow(
            "SELECT hunt_id, state, source, raw_input, boundary_usd FROM hunts WHERE hunt_id = $1",
            hunt_id,
        )
        if row is None:
            return None
        return {
            "hunt_id": row["hunt_id"],
            "state": row["state"],
            "source": row["source"],
            "raw_input": row["raw_input"] or "",
            "boundary_usd": row["boundary_usd"],
            "last_seq": await self.get_last_seq(hunt_id),
        }

    async def list_hunts(self, limit: int = 50) -> list[dict[str, Any]]:
        """Most-recent hunts first — powers the Den (Past Hunts)."""
        rows = await self._pool.fetch(
            """
            SELECT hunt_id, state, source, raw_input, boundary_usd, created_at
            FROM hunts ORDER BY created_at DESC LIMIT $1
            """,
            limit,
        )
        return [
            {
                "hunt_id": r["hunt_id"],
                "state": r["state"],
                "source": r["source"],
                "title": (r["raw_input"] or "").strip()[:80] or "Untitled hunt",
                "boundary_usd": r["boundary_usd"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    # --- events (the log + the outbox) -------------------------------------------------

    async def get_last_seq(self, hunt_id: str) -> int:
        """Highest seq for a hunt, or -1 if none yet (so the Emitter starts at 0)."""
        val = await self._pool.fetchval("SELECT MAX(seq) FROM events WHERE hunt_id = $1", hunt_id)
        return -1 if val is None else int(val)

    async def append_event(self, event: Event) -> None:
        """Insert the event and notify the relay, atomically.

        The (hunt_id, seq) primary key rejects any duplicate seq — that rejection, not the
        Emitter's in-memory lock, is the real gap-free guarantee.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO events (hunt_id, seq, event_id, ts, type, actor, payload)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    event.hunt_id,
                    event.seq,
                    event.event_id,
                    event.ts,
                    event.type,
                    event.actor,
                    event.payload,
                )
                await conn.execute("SELECT pg_notify($1, $2)", NOTIFY_CHANNEL, event.hunt_id)

    async def fetch_unrelayed(self, limit: int = 500) -> list[Event]:
        """Committed-but-unpublished events, in per-hunt seq order (the relay's work list)."""
        rows = await self._pool.fetch(
            """
            SELECT hunt_id, seq, event_id, ts, type, actor, payload
            FROM events
            WHERE relayed = FALSE
            ORDER BY hunt_id, seq
            LIMIT $1
            """,
            limit,
        )
        return [
            Event(
                event_id=r["event_id"],
                hunt_id=r["hunt_id"],
                seq=r["seq"],
                ts=r["ts"],
                type=r["type"],
                actor=r["actor"],
                payload=r["payload"],
            )
            for r in rows
        ]

    async def mark_relayed(self, hunt_id: str, seq: int) -> None:
        await self._pool.execute(
            "UPDATE events SET relayed = TRUE WHERE hunt_id = $1 AND seq = $2",
            hunt_id,
            seq,
        )

    async def replay_events(self, hunt_id: str, from_seq: int = 0) -> list[Event]:
        """Read the log straight from Postgres (the source of truth) — used by tests/tools."""
        rows = await self._pool.fetch(
            """
            SELECT hunt_id, seq, event_id, ts, type, actor, payload
            FROM events WHERE hunt_id = $1 AND seq >= $2 ORDER BY seq
            """,
            hunt_id,
            from_seq,
        )
        return [
            Event(
                event_id=r["event_id"],
                hunt_id=r["hunt_id"],
                seq=r["seq"],
                ts=r["ts"],
                type=r["type"],
                actor=r["actor"],
                payload=r["payload"],
            )
            for r in rows
        ]

    # --- artifacts ---------------------------------------------------------------------

    async def save_artifact(
        self,
        artifact_id: str,
        hunt_id: str,
        kind: str,
        produced_by: str | None,
        content: dict[str, Any] | None,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO artifacts (artifact_id, hunt_id, kind, produced_by, content)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (artifact_id) DO NOTHING
            """,
            artifact_id,
            hunt_id,
            kind,
            produced_by,
            content,
        )

    async def get_final_artifact(self, hunt_id: str) -> dict[str, Any] | None:
        """The hunt's final artifact (Howler's draft) for the reading view, or None."""
        row = await self._pool.fetchrow(
            """
            SELECT artifact_id, hunt_id, kind, produced_by, content
            FROM artifacts WHERE hunt_id = $1 AND kind = 'final'
            ORDER BY created_at DESC LIMIT 1
            """,
            hunt_id,
        )
        if row is None:
            return None
        return {
            "artifact_id": row["artifact_id"],
            "hunt_id": row["hunt_id"],
            "kind": row["kind"],
            "produced_by": row["produced_by"],
            "content": row["content"],
        }

    # --- instincts (the Den) -----------------------------------------------------------

    async def list_instincts(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            "SELECT instinct_id, label, spec FROM instincts ORDER BY created_at DESC"
        )
        return [
            {"instinct_id": r["instinct_id"], "label": r["label"], "spec": r["spec"]} for r in rows
        ]

    async def save_instinct(self, instinct_id: str, label: str, spec: dict[str, Any]) -> None:
        await self._pool.execute(
            """
            INSERT INTO instincts (instinct_id, label, spec)
            VALUES ($1, $2, $3)
            ON CONFLICT (instinct_id) DO UPDATE SET label = $2, spec = $3
            """,
            instinct_id,
            label,
            spec,
        )

    # --- checkpoints (stub now; resume logic NEXT) -------------------------------------

    async def save_checkpoint(
        self, checkpoint_id: str, hunt_id: str, at_seq: int, state: dict[str, Any]
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO checkpoints (checkpoint_id, hunt_id, at_seq, state)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (checkpoint_id) DO NOTHING
            """,
            checkpoint_id,
            hunt_id,
            at_seq,
            state,
        )
