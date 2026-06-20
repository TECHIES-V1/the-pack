"""The Emitter's core invariant: seq is dense, 0-based, and gap-free under concurrency.

No Postgres needed — an in-memory FakeRepo stands in. The real (hunt_id, seq) PK enforces
the same uniqueness in production.
"""

from __future__ import annotations

import asyncio

from app.engine.core import Emitter

from ._fakes import FakeRepo


def _warn(pct: float) -> dict:
    return {"pct": pct, "cumulative_usd": 0.1}


async def test_concurrent_emits_are_dense_and_ordered() -> None:
    repo = FakeRepo()
    emitter = Emitter("hunt_x", repo)

    # Fire 50 emits concurrently; the per-hunt lock must serialise seq assignment.
    await asyncio.gather(
        *(emitter.emit("boundary_warning", "engine", _warn(float(i))) for i in range(50))
    )

    seqs = [e.seq for e in repo.all_events("hunt_x")]
    assert seqs == list(range(50)), "seq must be dense, 0-based, gap-free"
    assert emitter.last_seq == 49


async def test_resume_continues_at_max_plus_one() -> None:
    repo = FakeRepo()
    first = Emitter("hunt_y", repo)
    for _ in range(5):
        await first.emit("boundary_warning", "engine", _warn(10.0))

    # A fresh Emitter (e.g. after a restart) must seed from the store, not from zero.
    second = Emitter("hunt_y", repo)
    ev = await second.emit("boundary_warning", "engine", _warn(20.0))
    assert ev.seq == 5
    assert [e.seq for e in repo.all_events("hunt_y")] == list(range(6))


async def test_invalid_payload_is_rejected_before_store() -> None:
    repo = FakeRepo()
    emitter = Emitter("hunt_z", repo)

    # boundary_warning requires pct + cumulative_usd; omit them.
    try:
        await emitter.emit("boundary_warning", "engine", {"nope": True})
        raise AssertionError("expected a schema violation")
    except ValueError as exc:
        assert "frozen schema" in str(exc)

    # Nothing was written, and seq did not advance.
    assert repo.all_events("hunt_z") == []
    assert emitter.last_seq == -1
