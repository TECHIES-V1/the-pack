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
from collections.abc import AsyncIterator, Awaitable, Callable

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

# A streaming sink the caller (Supervisor) supplies to observe text as it arrives, so it can
# emit throttled `wolf_progress` beats to the canvas. None => no streaming observation.
OnDelta = Callable[[str], Awaitable[None]]


def _loads_lenient(text: str) -> dict | None:
    """Parse a model's structured-output JSON, tolerating the two things models do that strict
    json.loads rejects: real newlines/control chars inside string values (strict=False), and a
    stray ```fence or prose around the object. Returns None only if there's no usable object."""
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").split("\n", 1)[-1]
    candidates = [stripped]
    if "{" in stripped and "}" in stripped:
        candidates.append(stripped[stripped.find("{") : stripped.rfind("}") + 1])
    for candidate in candidates:
        try:
            obj = json.loads(candidate, strict=False)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


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

    async def complete(
        self, spec: CallSpec, on_delta: OnDelta | None = None
    ) -> CompletionResult:
        """Run one completion through the chokepoint. Offline → FakeQwen; online → Qwen.

        `on_delta`, if given, is awaited with each text fragment as it streams (and once with
        the full text for non-streamed calls), so the Supervisor can narrate live progress.
        """
        if self.offline:
            return await self._fake.complete(spec, on_delta)
        return await self._complete_real(spec, on_delta)

    async def _complete_real(
        self, spec: CallSpec, on_delta: OnDelta | None = None
    ) -> CompletionResult:
        model = self._model(spec.tier)
        extra_body: dict = {}
        if spec.thinking:
            extra_body["enable_thinking"] = True
            if spec.thinking_budget is not None:
                extra_body["thinking_budget"] = spec.thinking_budget

        response_format = self._response_format(spec)
        must_stream = spec.thinking or spec.force_stream  # thinking always needs stream; force_stream opts in without thinking

        last_exc: Exception | None = None
        for attempt in range(settings.qwen_max_retries + 1):
            self._breaker.before()
            try:
                if must_stream:
                    result = await self._stream(model, spec, extra_body, response_format, on_delta)
                else:
                    result = await self._once(model, spec, extra_body, response_format, on_delta)
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
        self,
        model: str,
        spec: CallSpec,
        extra_body: dict,
        response_format: dict | None,
        on_delta: OnDelta | None = None,
    ) -> CompletionResult:
        resp = await self._client.chat.completions.create(  # type: ignore[union-attr]
            model=model,
            messages=spec.messages or [],
            extra_body=extra_body or None,
            response_format=response_format,
        )
        text = resp.choices[0].message.content or ""
        if on_delta and text:  # non-streamed call still surfaces one progress beat
            await on_delta(text)
        usage = resp.usage
        return self._account(spec, model, text, usage.prompt_tokens, usage.completion_tokens)

    async def _stream(
        self,
        model: str,
        spec: CallSpec,
        extra_body: dict,
        response_format: dict | None,
        on_delta: OnDelta | None = None,
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
                delta = chunk.choices[0].delta.content
                chunks.append(delta)
                if on_delta:
                    await on_delta(delta)
            if getattr(chunk, "usage", None):  # final chunk carries usage
                in_tokens = chunk.usage.prompt_tokens
                out_tokens = chunk.usage.completion_tokens
        return self._account(spec, model, "".join(chunks), in_tokens, out_tokens)

    def _account(
        self, spec: CallSpec, model: str, text: str, in_tokens: int, out_tokens: int
    ) -> CompletionResult:
        parsed: dict | None = None
        if spec.response_schema is not None:
            parsed = _loads_lenient(text)  # caller decides how to handle a non-JSON answer
        return CompletionResult(
            text=text,
            model=model,
            tier=spec.tier,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cost_usd=pricing.cost(spec.tier, in_tokens, out_tokens),
            parsed=parsed,
        )
