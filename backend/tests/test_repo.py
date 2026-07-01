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


async def test_read_path_indexes_exist(pg_pool) -> None:
    """B2: the additive read-path indexes are created by apply_schema."""
    rows = await pg_pool.fetch("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    names = {r["indexname"] for r in rows}
    for expected in (
        "idx_artifacts_hunt",
        "idx_messages_hunt",
        "idx_hunts_recent",
        "idx_events_completed",
    ):
        assert expected in names, f"missing index {expected}"


async def test_spend_summary_reads_terminal_totals(pg_pool) -> None:
    """B3: spend_summary joins each hunt to its terminal hunt_completed total in one pass."""
    repo = Repo(pg_pool)
    hunt_id = new_hunt_id()
    await repo.create_hunt(hunt_id, "typed", "the spend test topic")
    emitter = Emitter(hunt_id, repo)
    await emitter.emit(
        "hunt_completed",
        "engine",
        {"final_artifact_id": "art_x", "totals": {"cost_usd": 0.1234, "sources": 3}},
    )
    summary = await repo.spend_summary()
    mine = next((r for r in summary if r["hunt_id"] == hunt_id), None)
    assert mine is not None and mine["cost_usd"] == 0.1234
    assert "spend test topic" in mine["title"]


async def test_list_hunts_cursor_pagination(pg_pool) -> None:
    """B4: cursor pages backward through hunts by created_at."""
    repo = Repo(pg_pool)
    ids = []
    for i in range(3):
        hid = new_hunt_id()
        await repo.create_hunt(hid, "typed", f"pagination topic {i}")
        ids.append(hid)
    page1 = await repo.list_hunts(limit=2)
    assert len(page1) == 2
    cursor = f"{page1[-1]['created_at']}|{page1[-1]['hunt_id']}"
    page2 = await repo.list_hunts(limit=2, cursor=cursor)
    # The cursor strictly pages older, so page2 doesn't repeat page1's rows.
    assert {h["hunt_id"] for h in page1}.isdisjoint({h["hunt_id"] for h in page2})
