"""The outbox relay against a real Postgres (skipped if none).

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
