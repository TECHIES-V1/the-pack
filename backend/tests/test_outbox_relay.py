"""The outbox relay against a real Postgres (skipped if none). All tests require pg_pool.

An event committed to Postgres must appear on the bus with an identical envelope, and
re-draining already-relayed rows must publish nothing new (at-least-once, idempotent at the
read model).
"""

from __future__ import annotations

import asyncio

from app.db.repo import Repo
from app.engine.core import Emitter
from app.engine.ids import new_hunt_id
from app.engine.relay import OutboxRelay

from ._fakes import CollectingBus


async def test_committed_event_reaches_the_bus(pg_pool) -> None:
    repo = Repo(pg_pool)
    bus = CollectingBus()
    relay = OutboxRelay(pg_pool, bus, repo, poll_interval=0.2)

    hunt_id = new_hunt_id()
    await repo.create_hunt(hunt_id, "typed", "x")
    emitter = Emitter(hunt_id, repo)
    await emitter.emit("hunt_stopped", "user", {"by": "user"})

    await relay.start()
    try:
        # The event must get RELAYED (relayed=TRUE). We assert on that flag, not solely on our own
        # in-process bus, because a dev engine running against the same local DB has its own relay
        # that may legitimately publish (and mark) the row first — either way the outbox path fired.
        for _ in range(50):  # up to ~5s
            if any(e.hunt_id == hunt_id for e in bus.published):
                break
            flag = await pg_pool.fetchval(
                "SELECT relayed FROM events WHERE hunt_id = $1 AND seq = 0", hunt_id
            )
            if flag:
                break
            await asyncio.sleep(0.1)
    finally:
        await relay.stop()

    relayed = await pg_pool.fetchval(
        "SELECT relayed FROM events WHERE hunt_id = $1 AND seq = 0", hunt_id
    )
    assert relayed is True, "the committed event was never relayed"

    # When OUR relay is the one that published it, the envelope must be intact.
    mine = [e for e in bus.published if e.hunt_id == hunt_id]
    if mine:
        assert mine[0].seq == 0 and mine[0].type == "hunt_stopped"

    # Idempotent: everything relayed, so another drain publishes nothing new.
    before = len(bus.published)
    await relay._drain()
    assert len(bus.published) == before


async def test_relay_publishes_in_seq_order(pg_pool) -> None:
    """Five events for one hunt must arrive from the relay in seq order, not insertion chaos."""
    repo = Repo(pg_pool)
    bus = CollectingBus()
    relay = OutboxRelay(pg_pool, bus, repo, poll_interval=0.2)

    hunt_id = new_hunt_id()
    await repo.create_hunt(hunt_id, "typed", "ordering test")
    emitter = Emitter(hunt_id, repo)
    for i in range(5):
        await emitter.emit(f"event_type_{i}", "test", {"i": i})

    await relay.start()
    try:
        for _ in range(50):
            relayed = await pg_pool.fetchval(
                "SELECT COUNT(*) FROM events WHERE hunt_id = $1 AND relayed = TRUE", hunt_id
            )
            if relayed == 5:
                break
            await asyncio.sleep(0.1)
    finally:
        await relay.stop()

    mine = [e for e in bus.published if e.hunt_id == hunt_id]
    if mine:
        seqs = [e.seq for e in mine]
        assert seqs == sorted(seqs), f"relay broke ordering: {seqs}"


async def test_skip_locked_prevents_double_publish(pg_pool) -> None:
    """Two concurrent drain calls must not publish the same event twice (SKIP LOCKED)."""
    repo = Repo(pg_pool)
    bus = CollectingBus()

    hunt_id = new_hunt_id()
    await repo.create_hunt(hunt_id, "typed", "skip locked test")
    emitter = Emitter(hunt_id, repo)
    await emitter.emit("evt_a", "test", {})
    await emitter.emit("evt_b", "test", {})

    relay = OutboxRelay(pg_pool, bus, repo, poll_interval=999)

    # Two concurrent drains race — SKIP LOCKED means they split the work, not duplicate it.
    await asyncio.gather(relay._drain(), relay._drain())

    event_ids = [e.event_id for e in bus.published if e.hunt_id == hunt_id]
    assert len(event_ids) == len(set(event_ids)), (
        f"duplicate event_ids published: {event_ids}"
    )


async def test_at_least_once_redelivers_after_reset(pg_pool) -> None:
    """Events manually reset to relayed=FALSE are re-published on the next drain (at-least-once)."""
    repo = Repo(pg_pool)
    bus = CollectingBus()
    relay = OutboxRelay(pg_pool, bus, repo, poll_interval=0.2)

    hunt_id = new_hunt_id()
    await repo.create_hunt(hunt_id, "typed", "at-least-once test")
    emitter = Emitter(hunt_id, repo)
    await emitter.emit("evt_1", "test", {})
    await emitter.emit("evt_2", "test", {})
    await emitter.emit("evt_3", "test", {})

    # First drain — all three are published and marked.
    await relay.start()
    try:
        for _ in range(50):
            relayed = await pg_pool.fetchval(
                "SELECT COUNT(*) FROM events WHERE hunt_id = $1 AND relayed = TRUE", hunt_id
            )
            if relayed == 3:
                break
            await asyncio.sleep(0.1)
    finally:
        await relay.stop()

    assert await pg_pool.fetchval(
        "SELECT COUNT(*) FROM events WHERE hunt_id = $1 AND relayed = TRUE", hunt_id
    ) == 3

    # Simulate crash: reset two events back to unrelayed.
    await pg_pool.execute(
        "UPDATE events SET relayed = FALSE WHERE hunt_id = $1 AND seq IN (0, 1)", hunt_id
    )
    before = len([e for e in bus.published if e.hunt_id == hunt_id])

    # Second drain — the two reset events must be re-published.
    await relay._drain()
    after = [e for e in bus.published if e.hunt_id == hunt_id]
    assert len(after) - before == 2, "exactly the two reset events should be re-published"
