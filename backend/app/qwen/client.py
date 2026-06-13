"""The Qwen client — the single chokepoint every model call passes through (Doc 04 §04).

Responsibilities (scaffold; flesh out Jun 13-15):
  * Model-tier registry: max / plus / flash, resolved from config (never hard-coded names).
  * Per-call thinking mode + thinking budget, passed via the client's extra-body path
    (Qwen-only params: the thinking flag, top_k).
  * Token-accounting middleware that emits a `tokens_spent` event on every response.
  * Retries with backoff + a circuit breaker.
  * Structured output enforced for handoffs (one JSON schema per message intent).

ONE GOTCHA, baked in from day one: turning thinking ON requires streaming. A non-streamed
thinking call FAILS. So all thinking-mode wolves stream — which also gives live token
counts for the Boundary. See `complete()` below.

We point the OpenAI Python SDK at Qwen's OpenAI-compatible base URL. Verify real model
names + parameters in Model Studio on day 1 (F14) — do not trust memory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import TIER_REGISTRY, settings
from app.events.models import Event

# A callback the engine wires up so every completion emits a tokens_spent event.
EmitFn = Callable[[Event], Awaitable[None]]


@dataclass
class CallSpec:
    hunt_id: str
    wolf_id: str
    tier: str  # "max" | "plus" | "flash"
    thinking: bool = False
    thinking_budget: int | None = None
    messages: list[dict] | None = None
    response_schema: dict | None = None  # structured output for handoffs


class QwenClient:
    def __init__(self, emit: EmitFn | None = None) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
        )
        self._emit = emit

    def _model(self, tier: str) -> str:
        try:
            return TIER_REGISTRY[tier]
        except KeyError as exc:  # pragma: no cover - guardrail
            raise ValueError(f"unknown model tier: {tier!r}") from exc

    async def complete(self, spec: CallSpec) -> str:
        """Run one completion through the chokepoint.

        If thinking is on we MUST stream (non-streamed thinking calls fail on Qwen).
        Streaming also yields live token deltas the Boundary consumes.
        """
        model = self._model(spec.tier)
        extra_body: dict = {}
        if spec.thinking:
            # Qwen-only params go through extra_body, not the OpenAI surface.
            extra_body["enable_thinking"] = True
            if spec.thinking_budget is not None:
                extra_body["thinking_budget"] = spec.thinking_budget

        must_stream = spec.thinking  # the gotcha
        # TODO(Jun 13-15): retries/backoff, circuit breaker, structured-output enforcement,
        # real token accounting -> emit tokens_spent. This is the scaffold seam.
        if must_stream:
            return await self._stream(model, spec, extra_body)
        resp = await self._client.chat.completions.create(
            model=model,
            messages=spec.messages or [],
            extra_body=extra_body or None,
        )
        await self._account(spec, resp)
        return resp.choices[0].message.content or ""

    async def _stream(self, model: str, spec: CallSpec, extra_body: dict) -> str:
        chunks: list[str] = []
        stream: AsyncIterator = await self._client.chat.completions.create(
            model=model,
            messages=spec.messages or [],
            stream=True,
            stream_options={"include_usage": True},
            extra_body=extra_body or None,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
            # TODO: read chunk.usage when present -> incremental tokens_spent for Boundary.
        return "".join(chunks)

    async def _account(self, spec: CallSpec, resp) -> None:
        """Emit a tokens_spent event. Wired by the engine via the emit callback."""
        if self._emit is None or getattr(resp, "usage", None) is None:
            return
        usage = resp.usage
        # NOTE: real USD pricing comes from a config table; placeholder math here.
        cost = 0.0
        await self._emit(
            Event(
                hunt_id=spec.hunt_id,
                seq=-1,  # the engine assigns the real seq on append
                type="tokens_spent",
                actor=spec.wolf_id,
                payload={
                    "wolf_id": spec.wolf_id,
                    "model": self._model(spec.tier),
                    "in_tokens": usage.prompt_tokens,
                    "out_tokens": usage.completion_tokens,
                    "cost_usd": cost,
                    "cumulative_usd": cost,
                },
            )
        )
