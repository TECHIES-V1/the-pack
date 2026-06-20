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
        for _ in range(50):  # up to ~5s for the relay to publish
            if any(e.hunt_id == hunt_id for e in bus.published):
                break
            await asyncio.sleep(0.1)
    finally:
        await relay.stop()

    mine = [e for e in bus.published if e.hunt_id == hunt_id]
    assert len(mine) == 1
    assert mine[0].seq == 0 and mine[0].type == "hunt_stopped"

    # Idempotent: everything is marked relayed, so another drain publishes nothing new.
    before = len(bus.published)
    await relay._drain()
    assert len(bus.published) == before
