"""In-memory test doubles — let the engine run with no Postgres and no Redis.

`FakeRepo` mimics the parts of `app.db.repo.Repo` the Emitter and Supervisor touch, keeping
events in a dict and rejecting duplicate seq the way the real (hunt_id, seq) primary key
would. `CollectingBus` mimics `EventBus.append` by appending to a list. Together they make
the seq/emitter/offline-hunt tests run instantly, with no infrastructure.
"""

from __future__ import annotations

from typing import Any

from app.events.models import Event


class FakeRepo:
    def __init__(self) -> None:
        self.events: dict[str, list[Event]] = {}
        self.hunts: dict[str, dict[str, Any]] = {}
        self.artifacts: list[dict[str, Any]] = []

    async def create_hunt(
        self, hunt_id: str, source: str, raw_input: str | None, strategy: str = "orchestrate"
    ) -> None:
        self.hunts[hunt_id] = {
            "state": "planning",
            "source": source,
            "raw_input": raw_input,
            "strategy": strategy,
        }

    async def set_hunt_state(self, hunt_id: str, state: str) -> None:
        self.hunts.setdefault(hunt_id, {})["state"] = state

    async def set_boundary(self, hunt_id: str, boundary_usd: float) -> None:
        self.hunts.setdefault(hunt_id, {})["boundary_usd"] = boundary_usd

    async def get_last_seq(self, hunt_id: str) -> int:
        evs = self.events.get(hunt_id, [])
        return evs[-1].seq if evs else -1

    async def append_event(self, event: Event) -> None:
        evs = self.events.setdefault(event.hunt_id, [])
        if any(e.seq == event.seq for e in evs):
            raise ValueError(f"duplicate seq {event.seq} for {event.hunt_id}")
        evs.append(event)

    async def save_artifact(
        self, artifact_id: str, hunt_id: str, kind: str, produced_by: str | None, content: Any
    ) -> None:
        self.artifacts.append({"artifact_id": artifact_id, "hunt_id": hunt_id, "kind": kind})

    async def save_checkpoint(
        self, checkpoint_id: str, hunt_id: str, at_seq: int, state: Any
    ) -> None:
        pass

    def all_events(self, hunt_id: str) -> list[Event]:
        return self.events.get(hunt_id, [])


class CollectingBus:
    """Stands in for EventBus — records what the relay would publish to Redis."""

    def __init__(self) -> None:
        self.published: list[Event] = []

    async def append(self, event: Event) -> str:
        self.published.append(event)
        return f"{event.seq}-0"
