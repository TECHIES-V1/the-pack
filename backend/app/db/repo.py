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

    async def create_hunt(
        self, hunt_id: str, source: str, raw_input: str | None, strategy: str = "orchestrate"
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO hunts (hunt_id, state, source, raw_input, strategy)
            VALUES ($1, 'planning', $2, $3, $4)
            ON CONFLICT (hunt_id) DO NOTHING
            """,
            hunt_id,
            source,
            raw_input,
            strategy,
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
            "SELECT hunt_id, state, source, raw_input, strategy, boundary_usd "
            "FROM hunts WHERE hunt_id = $1",
            hunt_id,
        )
        if row is None:
            return None
        return {
            "hunt_id": row["hunt_id"],
            "state": row["state"],
            "source": row["source"],
            "raw_input": row["raw_input"] or "",
            "strategy": row["strategy"],
            "boundary_usd": row["boundary_usd"],
            "last_seq": await self.get_last_seq(hunt_id),
        }

    async def list_hunts(
        self, limit: int = 50, project_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Most-recent, non-archived hunts first — powers the Den (Past Hunts). Optionally scoped
        to one project."""
        rows = await self._pool.fetch(
            """
            SELECT hunt_id, state, source, raw_input, title, boundary_usd, project_id, created_at
            FROM hunts
            WHERE archived = FALSE AND ($2::text IS NULL OR project_id = $2)
            ORDER BY created_at DESC LIMIT $1
            """,
            limit,
            project_id,
        )
        return [
            {
                "hunt_id": r["hunt_id"],
                "state": r["state"],
                "source": r["source"],
                "title": (r["title"] or (r["raw_input"] or "").strip()[:80]) or "Untitled hunt",
                "boundary_usd": r["boundary_usd"],
                "project_id": r["project_id"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def rename_hunt(self, hunt_id: str, title: str) -> None:
        await self._pool.execute(
            "UPDATE hunts SET title = $2, updated_at = now() WHERE hunt_id = $1", hunt_id, title
        )

    async def set_archived(self, hunt_id: str, archived: bool) -> None:
        await self._pool.execute(
            "UPDATE hunts SET archived = $2, updated_at = now() WHERE hunt_id = $1",
            hunt_id,
            archived,
        )

    async def delete_hunt(self, hunt_id: str) -> None:
        """Remove a hunt and everything hanging off it."""
        for tbl in ("messages", "events", "artifacts", "checkpoints"):
            await self._pool.execute(f"DELETE FROM {tbl} WHERE hunt_id = $1", hunt_id)
        await self._pool.execute("DELETE FROM hunts WHERE hunt_id = $1", hunt_id)

    # --- projects (workspaces that group hunts) ----------------------------------------

    async def list_projects(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT p.project_id, p.label, p.instructions, p.created_at,
                   COUNT(h.hunt_id) FILTER (WHERE h.archived = FALSE) AS hunt_count
            FROM projects p
            LEFT JOIN hunts h ON h.project_id = p.project_id
            GROUP BY p.project_id
            ORDER BY p.created_at DESC
            """
        )
        return [
            {
                "project_id": r["project_id"],
                "label": r["label"],
                "instructions": r["instructions"],
                "hunt_count": int(r["hunt_count"]),
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def create_project(self, project_id: str, label: str, instructions: str | None) -> None:
        await self._pool.execute(
            "INSERT INTO projects (project_id, label, instructions) VALUES ($1, $2, $3)",
            project_id,
            label,
            instructions,
        )

    async def update_project(
        self, project_id: str, label: str | None, instructions: str | None
    ) -> None:
        await self._pool.execute(
            """
            UPDATE projects SET label = COALESCE($2, label),
                                instructions = COALESCE($3, instructions)
            WHERE project_id = $1
            """,
            project_id,
            label,
            instructions,
        )

    async def delete_project(self, project_id: str) -> None:
        """Drop the project but keep its hunts — just unassign them."""
        await self._pool.execute(
            "UPDATE hunts SET project_id = NULL WHERE project_id = $1", project_id
        )
        await self._pool.execute("DELETE FROM projects WHERE project_id = $1", project_id)

    async def assign_hunt(self, hunt_id: str, project_id: str | None) -> None:
        await self._pool.execute(
            "UPDATE hunts SET project_id = $2, updated_at = now() WHERE hunt_id = $1",
            hunt_id,
            project_id,
        )

    # --- conversation messages (durable per-hunt chat) ---------------------------------

    async def save_message(self, hunt_id: str, role: str, content: str) -> None:
        seq = await self._pool.fetchval(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM messages WHERE hunt_id = $1", hunt_id
        )
        await self._pool.execute(
            "INSERT INTO messages (hunt_id, seq, role, content) VALUES ($1, $2, $3, $4)",
            hunt_id,
            int(seq),
            role,
            content,
        )

    async def list_messages(self, hunt_id: str) -> list[dict[str, str]]:
        rows = await self._pool.fetch(
            "SELECT role, content FROM messages WHERE hunt_id = $1 ORDER BY seq", hunt_id
        )
        return [{"role": r["role"], "text": r["content"]} for r in rows]

    # --- sharing (public read-only link to a returned brief) ---------------------------

    async def set_share_token(self, hunt_id: str, token: str) -> None:
        await self._pool.execute(
            "UPDATE hunts SET share_token = $2 WHERE hunt_id = $1", hunt_id, token
        )

    async def get_shared(self, token: str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            "SELECT hunt_id, title, raw_input FROM hunts WHERE share_token = $1", token
        )
        if row is None:
            return None
        artifact = await self.get_final_artifact(row["hunt_id"])
        content = artifact["content"] if artifact else None
        title = (row["title"] or (row["raw_input"] or "").strip()[:80]) or "A Pack brief"
        return {"title": title, "content": content}

    # --- events (the log + the outbox) -------------------------------------------------

    async def get_last_seq(self, hunt_id: str) -> int:
        """Highest seq for a hunt, or -1 if none yet (so the Emitter starts at 0)."""
        val = await self._pool.fetchval("SELECT MAX(seq) FROM events WHERE hunt_id = $1", hunt_id)
        return -1 if val is None else int(val)

    async def list_unfinished_hunts(self) -> list[dict[str, Any]]:
        """Hunts in a non-terminal state — used on startup to reconcile any orphaned by a prior stop
        (their in-memory Supervisor is gone)."""
        rows = await self._pool.fetch(
            """
            SELECT hunt_id, state FROM hunts
            WHERE state NOT IN ('returned', 'failed', 'stopped_by_user')
            """
        )
        return [{"hunt_id": r["hunt_id"], "state": r["state"]} for r in rows]

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

    async def list_artifacts(self, hunt_id: str) -> list[dict[str, Any]]:
        """All artifacts for a hunt (id + kind) — the Reward's format tabs (v3)."""
        rows = await self._pool.fetch(
            "SELECT artifact_id, kind FROM artifacts WHERE hunt_id = $1 ORDER BY created_at",
            hunt_id,
        )
        return [{"artifact_id": r["artifact_id"], "kind": r["kind"]} for r in rows]

    async def get_artifact_row(self, artifact_id: str) -> dict[str, Any] | None:
        """One artifact by id (for downloading a forged file), or None."""
        row = await self._pool.fetchrow(
            "SELECT artifact_id, hunt_id, kind, content FROM artifacts WHERE artifact_id = $1",
            artifact_id,
        )
        if row is None:
            return None
        return {
            "artifact_id": row["artifact_id"],
            "hunt_id": row["hunt_id"],
            "kind": row["kind"],
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

    async def get_instinct(self, instinct_id: str) -> dict[str, Any] | None:
        """One saved instinct (preset) by id, or None — used to seed a hunt from the Den."""
        row = await self._pool.fetchrow(
            "SELECT instinct_id, label, spec FROM instincts WHERE instinct_id = $1", instinct_id
        )
        if row is None:
            return None
        return {"instinct_id": row["instinct_id"], "label": row["label"], "spec": row["spec"]}

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

    # --- memory (v2): what the pack learned across hunts (local-only) ------------------

    async def save_memory(self, hunt_id: str | None, kind: str, text: str) -> None:
        await self._pool.execute(
            "INSERT INTO memory (hunt_id, kind, text) VALUES ($1, $2, $3)", hunt_id, kind, text
        )

    async def recent_memory(self, limit: int = 5) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            "SELECT hunt_id, kind, text FROM memory ORDER BY id DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]

    # --- knowledge base (your documents, v4.2) -----------------------------------------

    async def save_document(self, name: str, kind: str, text: str) -> int:
        row = await self._pool.fetchrow(
            "INSERT INTO documents (name, kind, text, chars) VALUES ($1, $2, $3, $4) RETURNING id",
            name,
            kind,
            text,
            len(text),
        )
        return int(row["id"])

    async def list_documents(self, *, with_text: bool = False) -> list[dict[str, Any]]:
        cols = "id, name, kind, chars" + (", text" if with_text else "")
        rows = await self._pool.fetch(f"SELECT {cols} FROM documents ORDER BY id DESC")
        return [dict(r) for r in rows]

    async def delete_document(self, doc_id: int) -> None:
        await self._pool.execute("DELETE FROM documents WHERE id = $1", doc_id)

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

    # --- feedback ----------------------------------------------------------------------

    async def save_feedback(self, hunt_id: str, turn_index: int, vote: str) -> None:
        await self._pool.execute(
            """
            INSERT INTO feedback (hunt_id, turn_index, vote)
            VALUES ($1, $2, $3)
            """,
            hunt_id,
            turn_index,
            vote,
        )
