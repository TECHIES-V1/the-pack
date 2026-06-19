"""The Qwen client — the single chokepoint every model call passes through (Doc 04 §04).

One place, so every call gets: tier resolution, per-call thinking mode, real token
accounting, retries + backoff, a circuit breaker, and structured output. We point the
OpenAI Python SDK at Qwen's OpenAI-compatible base URL.

THE OFFLINE SWITCH: if there is no `QWEN_API_KEY`, the client routes every call to the
deterministic `FakeQwen` instead of the network. The whole system runs without a key today;
the moment the key lands the client uses the real model — **zero change** to the Supervisor
or the event stream.

THE GOTCHA, baked in: turning thinking ON requires streaming. A non-streamed thinking call
FAILS on Qwen. So thinking-mode wolves stream — which also yields live token counts.

The client RETURNS a `CompletionResult` (text + usage + cost). It never emits events itself
— the Supervisor turns the result into a `tokens_spent` event through the one Emitter, so
seq assignment stays in one place.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from app.config import TIER_REGISTRY, settings
from app.qwen import pricing
from app.qwen.fake import FakeQwen
from app.qwen.types import CallSpec, CompletionResult

# Errors worth retrying: transient/transport/5xx/rate-limit. Never 4xx (bad request) —
# retrying a malformed call just wastes budget.
_TRANSIENT = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)


class CircuitOpenError(RuntimeError):
    """Raised when the breaker is open — fail fast instead of hammering a dead endpoint."""


class _Breaker:
    """A tiny circuit breaker: open after N consecutive failures, cool down, then retry."""

    def __init__(self, threshold: int, cooldown_s: float) -> None:
        self._threshold = threshold
        self._cooldown_s = cooldown_s
        self._failures = 0
        self._opened_at: float | None = None

    def before(self) -> None:
        if self._opened_at is None:
            return
        if time.monotonic() - self._opened_at < self._cooldown_s:
            raise CircuitOpenError("Qwen circuit breaker is open")
        # Cooldown elapsed — allow one trial call (half-open).
        self._opened_at = None

    def on_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = time.monotonic()


class QwenClient:
    def __init__(self) -> None:
        self.offline = not settings.qwen_api_key
        self._fake = FakeQwen()
        self._breaker = _Breaker(settings.qwen_breaker_threshold, settings.qwen_breaker_cooldown_s)
        self._client: AsyncOpenAI | None = None
        if not self.offline:
            self._client = AsyncOpenAI(
                api_key=settings.qwen_api_key,
                base_url=settings.qwen_base_url,
            )

    def _model(self, tier: str) -> str:
        try:
            return TIER_REGISTRY[tier]
        except KeyError as exc:  # pragma: no cover - guardrail
            raise ValueError(f"unknown model tier: {tier!r}") from exc

    async def complete(self, spec: CallSpec) -> CompletionResult:
        """Run one completion through the chokepoint. Offline → FakeQwen; online → Qwen."""
        if self.offline:
            return await self._fake.complete(spec)
        return await self._complete_real(spec)

    async def _complete_real(self, spec: CallSpec) -> CompletionResult:
        model = self._model(spec.tier)
        extra_body: dict = {}
        if spec.thinking:
            extra_body["enable_thinking"] = True
            if spec.thinking_budget is not None:
                extra_body["thinking_budget"] = spec.thinking_budget

        response_format = self._response_format(spec)
        must_stream = spec.thinking  # the gotcha

        last_exc: Exception | None = None
        for attempt in range(settings.qwen_max_retries + 1):
            self._breaker.before()
            try:
                if must_stream:
                    result = await self._stream(model, spec, extra_body, response_format)
                else:
                    result = await self._once(model, spec, extra_body, response_format)
                self._breaker.on_success()
                return result
            except _TRANSIENT as exc:  # retry these
                last_exc = exc
                self._breaker.on_failure()
                if attempt < settings.qwen_max_retries:
                    await asyncio.sleep(settings.qwen_backoff_base_s * (2**attempt))
                continue
        assert last_exc is not None
        raise last_exc

    def _response_format(self, spec: CallSpec) -> dict | None:
        if spec.response_schema is None:
            return None
        # Prefer strict json_schema; DashScope also honors json_object as a fallback.
        return {
            "type": "json_schema",
            "json_schema": {"name": spec.intent or "handoff", "schema": spec.response_schema},
        }

    async def _once(
        self, model: str, spec: CallSpec, extra_body: dict, response_format: dict | None
    ) -> CompletionResult:
        resp = await self._client.chat.completions.create(  # type: ignore[union-attr]
            model=model,
            messages=spec.messages or [],
            extra_body=extra_body or None,
            response_format=response_format,
        )
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return self._account(spec, model, text, usage.prompt_tokens, usage.completion_tokens)

    async def _stream(
        self, model: str, spec: CallSpec, extra_body: dict, response_format: dict | None
    ) -> CompletionResult:
        chunks: list[str] = []
        in_tokens = out_tokens = 0
        stream: AsyncIterator = await self._client.chat.completions.create(  # type: ignore[union-attr]
            model=model,
            messages=spec.messages or [],
            stream=True,
            stream_options={"include_usage": True},
            extra_body=extra_body or None,
            response_format=response_format,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
            if getattr(chunk, "usage", None):  # final chunk carries usage
                in_tokens = chunk.usage.prompt_tokens
                out_tokens = chunk.usage.completion_tokens
        return self._account(spec, model, "".join(chunks), in_tokens, out_tokens)

    def _account(
        self, spec: CallSpec, model: str, text: str, in_tokens: int, out_tokens: int
    ) -> CompletionResult:
        parsed: dict | None = None
        if spec.response_schema is not None:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None  # caller decides how to handle a non-JSON answer
        return CompletionResult(
            text=text,
            model=model,
            tier=spec.tier,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cost_usd=pricing.cost(spec.tier, in_tokens, out_tokens),
            parsed=parsed,
        )
