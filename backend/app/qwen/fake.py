"""FakeQwen — the deterministic, offline brain (Doc 04 §07, F14 fallback).

When there is no API key, the whole system still runs end to end: REST → Supervisor →
Emitter → Postgres → relay → Redis → gateway → canvas. The only thing swapped out is the
model call. FakeQwen returns canned-but-plausible text and *realistic synthetic usage* so
the Boundary meter actually moves and the demo looks real.

It is deterministic: same spec in, same result out (no clocks, no randomness), which is what
makes `test_offline_hunt` reproducible. The moment a real `QWEN_API_KEY` lands, `QwenClient`
stops routing here — zero change to the Supervisor or the event stream.
"""

from __future__ import annotations

from app.config import TIER_REGISTRY
from app.qwen import pricing
from app.qwen.types import CallSpec, CompletionResult

# Synthetic token usage per tier (input, output) — research-scale so cost is visible but a
# normal hunt stays comfortably inside a $0.50 first-hunt cap.
_USAGE_BY_TIER: dict[str, tuple[int, int]] = {
    "flash": (60_000, 12_000),
    "plus": (85_000, 17_000),
    "max": (40_000, 9_000),
}

_CANNED: dict[str, str] = {
    "plan": "Proposed a parallel_then_merge hunt: scouts range, tracker merges, howler drafts.",
    "search": "Found 3 sources with citations.",
    "merge": "Cross-referenced the scouts' findings; one conflict surfaced for a Hold.",
    "draft": "Drafted the briefing with inline citations to every source.",
    "critique": "Checked every claim carries a source; flagged none missing.",
}


class FakeQwen:
    """Stands in for the real model. Same `complete` signature as QwenClient."""

    async def complete(self, spec: CallSpec) -> CompletionResult:
        in_tokens, out_tokens = _USAGE_BY_TIER.get(spec.tier, _USAGE_BY_TIER["plus"])
        model = TIER_REGISTRY.get(spec.tier, spec.tier)
        text = _CANNED.get(spec.intent or "", f"[offline {spec.tier}] {spec.wolf_id} did its part.")
        parsed = {"intent": spec.intent, "summary": text} if spec.response_schema else None
        return CompletionResult(
            text=text,
            model=model,
            tier=spec.tier,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cost_usd=pricing.cost(spec.tier, in_tokens, out_tokens),
            parsed=parsed,
        )
