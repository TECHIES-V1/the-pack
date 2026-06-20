"""The Emitter — the one place an event is born (Doc 04 §3, §5).

Every event in the system passes through here. The Emitter:
  1. assigns the dense, 0-based, strictly-increasing `seq` for its hunt (under a lock),
  2. validates the full envelope against the FROZEN schema (events.schema.json),
  3. writes it to Postgres — and ONLY Postgres — in one transaction.

It does NOT touch Redis. Publishing to the stream is the outbox relay's job
(app/engine/relay.py). That separation is what makes the write atomic and kills the
dual-write problem: there is exactly one durable write in the hot path.

The per-hunt asyncio.Lock serialises concurrent wolf emits so seq stays gap-free
(`seqs == range(len)`, the contract invariant). The (hunt_id, seq) primary key in Postgres
is the real backstop — if two processes ever raced, the second insert would be rejected.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from app.db.repo import Repo
from app.events.models import Event, EventType, load_event_schema


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    """One compiled validator for the frozen schema, shared across all emitters."""
    return Draft202012Validator(load_event_schema())


class Emitter:
    """One per hunt. Owns that hunt's seq counter and emit lock."""

    def __init__(self, hunt_id: str, repo: Repo, *, validate: bool = True) -> None:
        self._hunt_id = hunt_id
        self._repo = repo
        self._lock = asyncio.Lock()
        self._next_seq: int | None = None  # seeded lazily from the store
        self._validate = validate

    @property
    def hunt_id(self) -> str:
        return self._hunt_id

    @property
    def last_seq(self) -> int:
        """The last seq emitted, or -1 before the first emit (mirrors the store)."""
        return -1 if self._next_seq is None else self._next_seq - 1

    async def _seed(self) -> None:
        if self._next_seq is None:
            self._next_seq = await self._repo.get_last_seq(self._hunt_id) + 1

    async def emit(self, type: EventType, actor: str, payload: dict[str, Any]) -> Event:
        """Mint, validate, and durably append one event. Returns the stored envelope."""
        async with self._lock:
            await self._seed()
            assert self._next_seq is not None
            event = Event(
                hunt_id=self._hunt_id,
                seq=self._next_seq,
                type=type,
                actor=actor,
                payload=payload,
            )
            if self._validate:
                self._check(event)
            await self._repo.append_event(event)
            self._next_seq += 1
            return event

    def _check(self, event: Event) -> None:
        errors = sorted(_validator().iter_errors(event.model_dump()), key=str)
        if errors:
            raise ValueError(
                f"event {event.type} (seq {event.seq}) violates the frozen schema: "
                f"{[e.message for e in errors]}"
            )
