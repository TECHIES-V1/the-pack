"""Pydantic v2 mirror of the frozen event envelope (schema/events.schema.json).

The JSON Schema is the source of truth and the frozen contract. This module gives the
engine a typed envelope to build and emit events, and a loader so the contract test (and
the engine's own self-checks) validate every event against that one schema.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from ulid import ULID

# Layout: backend/app/events/models.py  ->  backend/schema/events.schema.json
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "events.schema.json"

EventType = Literal[
    "hunt_created",
    "input_added",
    "transcript_ready",
    "plan_proposed",
    "plan_edited",
    "plan_approved",
    "wolf_spawned",
    "step_started",
    "step_completed",
    "message_passed",
    "wolf_progress",
    "tool_called",
    "tool_result",
    "tokens_spent",
    "hold_opened",
    "hold_resolved",
    "standoff_opened",
    "standoff_turn",
    "standoff_resolved",
    "stray_detected",
    "stray_recovered",
    "doctor_dispatched",
    "doctor_healed",
    "boundary_warning",
    "boundary_downgrade",
    "boundary_halt",
    "artifact_created",
    "forge_started",
    "forge_completed",
    "hunt_completed",
    "hunt_failed",
    "hunt_stopped",
    "benchmark_started",
    "benchmark_completed",
]

EVENT_TYPES: tuple[str, ...] = EventType.__args__  # type: ignore[attr-defined]


class Event(BaseModel):
    """The envelope (Doc 04 §3.1). seq is strictly increasing per hunt; append-only."""

    event_id: str = Field(default_factory=lambda: f"evt_{ULID()}")
    hunt_id: str
    seq: int = Field(ge=0)
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    type: EventType
    actor: str
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return self.model_dump_json()


@lru_cache(maxsize=1)
def load_event_schema() -> dict[str, Any]:
    """Load and cache the frozen JSON Schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
