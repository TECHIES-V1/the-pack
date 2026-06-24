"""Shared request/response types for the Qwen chokepoint.

Kept in their own module so the real client (`client.py`) and the offline provider
(`fake.py`) can both import them without a circular dependency.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CallSpec:
    hunt_id: str
    wolf_id: str
    tier: str  # "max" | "plus" | "flash"
    thinking: bool = False
    thinking_budget: int | None = None
    messages: list[dict] | None = None
    response_schema: dict | None = None  # structured output for handoffs
    intent: str | None = None  # a hint the fake provider keys its canned answer on
    force_stream: bool = False  # force streaming even when thinking mode is off


@dataclass
class CompletionResult:
    """What every call returns — content PLUS the accounting the Boundary needs.

    Crucially this carries usage/cost as plain data. The client never emits events itself
    (no more `Event(seq=-1)`); the Supervisor turns this into a `tokens_spent` event through
    the one Emitter, so seq stays correct.
    """

    text: str
    model: str
    tier: str
    in_tokens: int
    out_tokens: int
    cost_usd: float
    parsed: dict | None = None
