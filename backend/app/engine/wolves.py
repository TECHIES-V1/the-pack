"""A Wolf — one agent's identity + its line to the model (Doc 04 §04).

A Wolf is deliberately thin: who it is (id, role, tier, thinking, prompt_version) and a
`think()` that builds a CallSpec and goes through the QwenClient chokepoint. The same code
runs whether the client is offline (FakeQwen) or live (Qwen) — the Wolf can't tell and
doesn't care. The Boundary gate and event emission live in the Supervisor, not here, so a
Wolf can never dispatch a call that escaped the gate.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.qwen.client import QwenClient
from app.qwen.types import CallSpec, CompletionResult


@dataclass
class Wolf:
    hunt_id: str
    wolf_id: str
    role: str
    tier: str
    thinking: bool
    prompt_version: str
    client: QwenClient

    async def think(
        self,
        intent: str,
        *,
        messages: list[dict] | None = None,
        response_schema: dict | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> CompletionResult:
        spec = CallSpec(
            hunt_id=self.hunt_id,
            wolf_id=self.wolf_id,
            tier=self.tier,
            thinking=self.thinking,
            messages=messages,
            response_schema=response_schema,
            intent=intent,
        )
        return await self.client.complete(spec, on_delta)
