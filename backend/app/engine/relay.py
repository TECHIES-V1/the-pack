"""The outbox relay — Postgres → Redis, the only writer to the stream (Doc 04 §5).

This is the message-relay half of the transactional outbox. The Emitter writes events to
Postgres (the source of truth); this relay tails the committed-but-unpublished rows and
republishes each through the existing `EventBus.append` (unchanged Redis XADD + envelope),
then marks it relayed.

It wakes two ways:
  * `LISTEN pack_events` — Postgres delivers a notification on every committed append, so
    the relay publishes within milliseconds (the "live" path).
  * a periodic sweep (~1s) — a safety net that catches anything a missed/dropped
    notification left behind, and drains the backlog on startup.

Delivery is AT-LEAST-ONCE: _drain runs SELECT FOR UPDATE SKIP LOCKED → XADD → mark relayed all
inside one Postgres transaction. Two relay workers skip each other's locked rows. If the process
dies before XADD the txn rolls back and the row stays unrelayed for the next pass. If it dies
after commit the event is both published and marked — no loss. A duplicate publish (XADD ok,
commit fail) is a no-op because the frontend reducer drops seq <= lastSeq.
"""

from __future__ import annotations

import asyncio
import contextlib

import asyncpg

from app.bus.redis_stream import EventBus
from app.db.repo import NOTIFY_CHANNEL, Repo


class OutboxRelay:
    def __init__(
        self,
        pool: asyncpg.Pool,
        bus: EventBus,
        repo: Repo,
        *,
        poll_interval: float = 1.0,
    ) -> None:
        self._pool = pool
        self._bus = bus
        self._repo = repo
        self._poll_interval = poll_interval
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._listen_conn: asyncpg.Connection | None = None
        self._listen_lost = False

    async def start(self) -> None:
        """Acquire a dedicated LISTEN connection and spin up the drain loop."""
        await self._relisten()
        self._task = asyncio.create_task(self._run(), name="outbox-relay")

    async def _relisten(self) -> None:
        """(Re)establish the dedicated LISTEN connection. The periodic sweep covers any gap while
        the live notification path is down, so a dropped Postgres connection only costs latency."""
        conn = await self._pool.acquire()
        await conn.add_listener(NOTIFY_CHANNEL, self._on_notify)
        conn.add_termination_listener(self._on_listen_lost)
        self._listen_conn = conn
        self._listen_lost = False

    def _on_notify(self, *_args: object) -> None:
        # Fires on the asyncpg event loop; just nudge the loop awake.
        self._wake.set()

    def _on_listen_lost(self, _conn: object) -> None:
        # The LISTEN connection dropped — flag a re-listen and wake the loop to do it.
        self._listen_lost = True
        self._wake.set()

    async def _run(self) -> None:
        await self._drain()  # clear any startup backlog first
        while True:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self._poll_interval)
            except TimeoutError:
                pass  # periodic safety sweep
            self._wake.clear()
            if self._listen_lost:  # reconnect the live path; the sweep bridged the outage
                with contextlib.suppress(Exception):
                    await self._relisten()
            try:
                await self._drain()
            except Exception:  # noqa: BLE001 - the relay must never die on a transient error
                # Leave rows unrelayed; the next sweep retries (at-least-once).
                continue

    async def _drain(self) -> None:
        """Publish every unrelayed event, in order, until the outbox is empty.

        One Postgres transaction per batch:
          1. SELECT FOR UPDATE SKIP LOCKED — prevents two relay workers picking the same rows.
          2. XADD to Redis (inside the open transaction; if XADD throws, txn rolls back).
          3. Mark relayed and commit — both happen atomically.

        At-least-once: if the process dies before XADD (step 2), the txn rolls back and the
        row stays unrelayed → retry next pass. If it dies after commit → already published and
        marked → safe. The tiny window is: XADD succeeded but commit failed → re-publish on
        next pass (duplicate, harmless: the frontend reducer drops seq <= lastSeq).
        """
        while True:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    batch = await self._repo.fetch_unrelayed_locked(conn)
                    if not batch:
                        return
                    for event in batch:
                        await self._bus.append(event)
                    await self._repo.mark_batch_relayed(conn, batch)

    async def stop(self) -> None:
        """Cancel the loop, do one final drain so nothing is stranded, release the conn."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        with contextlib.suppress(Exception):
            await self._drain()
        if self._listen_conn is not None:
            with contextlib.suppress(Exception):
                await self._listen_conn.remove_listener(NOTIFY_CHANNEL, self._on_notify)
            await self._pool.release(self._listen_conn)
            self._listen_conn = None
