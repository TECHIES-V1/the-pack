"""Repo against a real Postgres (skipped if none): the (hunt_id, seq) PK rejects dup seq."""

from __future__ import annotations

import asyncpg
import pytest

from app.db.repo import Repo
from app.engine.core import Emitter
from app.engine.ids import new_hunt_id
from app.events.models import Event


async def test_duplicate_seq_is_rejected(pg_pool) -> None:
    repo = Repo(pg_pool)
    hunt_id = new_hunt_id()
    await repo.create_hunt(hunt_id, "typed", "x")

    first = Event(hunt_id=hunt_id, seq=0, type="hunt_stopped", actor="user", payload={"by": "user"})
    await repo.append_event(first)

    # A second event at the same seq must be rejected by the primary key.
    clash = Event(hunt_id=hunt_id, seq=0, type="hunt_stopped", actor="user", payload={"by": "user"})
    with pytest.raises(asyncpg.UniqueViolationError):
        await repo.append_event(clash)

    assert await repo.get_last_seq(hunt_id) == 0


async def test_emitter_persists_and_snapshot_reads_back(pg_pool) -> None:
    repo = Repo(pg_pool)
    hunt_id = new_hunt_id()
    await repo.create_hunt(hunt_id, "typed", "BNPL")
    emitter = Emitter(hunt_id, repo)

    for _ in range(3):
        await emitter.emit("boundary_warning", "engine", {"pct": 50.0, "cumulative_usd": 0.1})

    snap = await repo.get_hunt_snapshot(hunt_id)
    assert snap is not None
    assert snap["last_seq"] == 2
    events = await repo.replay_events(hunt_id, 0)
    assert [e.seq for e in events] == [0, 1, 2]
