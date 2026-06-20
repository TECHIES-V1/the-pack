"""FakeQwen — the deterministic, offline brain (Doc 04 §07, F14 fallback).

When there is no API key, the whole system still runs end to end: REST → Supervisor →
Emitter → Postgres → relay → Redis → gateway → canvas. The only thing swapped out is the
model call. FakeQwen returns canned-but-plausible text AND, for the structured calls the real
engine makes (plan, findings, merge, critique, gaps), a deterministic object SHAPED LIKE the
requested `response_schema` and woven from the actual task — so the dynamic engine exercises
the same code path offline, topic-aware, with realistic synthetic usage so the Boundary moves.

It is deterministic: same spec in, same result out (no clocks, no randomness). The moment a
real `QWEN_API_KEY` lands, `QwenClient` stops routing here — zero change to the Supervisor or
the event stream.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

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


def _task_of(spec: CallSpec) -> str:
    """Pull the task out of the user message the Supervisor builds ("Task: …")."""
    for m in reversed(spec.messages or []):
        if m.get("role") == "user":
            content = str(m.get("content", ""))
            if content.startswith("Task:"):
                return content[len("Task:") :].split("\n", 1)[0].strip() or "the topic"
            return (content.split("\n", 1)[0].strip() or "the topic")[:120]
    return "the topic"


def _offline_result(intent: str, task: str) -> tuple[str, dict | None]:
    """Deterministic (text, parsed) for one intent, woven from the task. parsed is None for
    free-text intents (draft, chat) and a schema-shaped object for the structured ones."""
    if intent == "plan":
        parsed = {
            "summary": f"A parallel research plan on {task}: range on three angles, merge, draft.",
            "queries": [
                f"{task} — overview and key players",
                f"{task} — latest data and figures",
                f"{task} — risks, context, and outlook",
            ],
            "assumptions": [f"scope: {task}", "recent sources", "briefing format"],
            "est_cost": 0.6,
            "est_time": 210,
        }
        return parsed["summary"], parsed
    if intent == "search":
        text = f"Found and summarized the key findings on {task}, each tied to a source."
        return text, {"summary": text, "confidence": 0.82}
    if intent == "merge":
        text = f"Cross-referenced the scouts' findings on {task}; the sources line up."
        parsed = {
            "summary": text,
            "claims": [
                f"{task}: the leading players and the shape of the landscape.",
                f"{task}: the most recent figures the sources agree on.",
                f"{task}: the key risk and what to watch next.",
            ],
            "conflict": None,
        }
        return text, parsed
    if intent == "critique":
        # Offline, Sentinel raises one challenge so the critique mode visibly does its job.
        parsed = {
            "ok": False,
            "issues": [
                {
                    "claim": f"the most recent figures on {task}",
                    "problem": "rests on a single source — needs a second to stand.",
                }
            ],
        }
        return "Challenged the weakest claim: it needs a second source.", parsed
    if intent == "gaps":
        parsed = {
            "gaps": [
                f"{task} — the missing quantitative detail",
                f"{task} — the most recent development",
            ]
        }
        return "Two gaps remain; sending the pack back in.", parsed
    if intent == "draft":
        text = (
            f"# Briefing: {task}\n\n"
            f"This briefing summarizes what the pack found on {task}, with sources.\n\n"
            "## Key points\n"
            f"- The landscape and the leading players in {task}.\n"
            f"- The most recent figures the sources agree on.\n"
            f"- The key risk and what to watch next.\n\n"
            "Every claim above traces to a scout's cited source."
        )
        return text, None
    return f"[offline] {intent} on {task}.", None


class FakeQwen:
    """Stands in for the real model. Same `complete` signature as QwenClient."""

    async def complete(
        self,
        spec: CallSpec,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> CompletionResult:
        in_tokens, out_tokens = _USAGE_BY_TIER.get(spec.tier, _USAGE_BY_TIER["plus"])
        model = TIER_REGISTRY.get(spec.tier, spec.tier)
        task = _task_of(spec)
        text, parsed = _offline_result(spec.intent or "", task)
        # Structured calls must return a parsed object; free-text calls return None.
        if spec.response_schema is None:
            parsed = None
        if on_delta and text:  # mirror the live path: surface one progress beat offline too
            await on_delta(text)
        return CompletionResult(
            text=text,
            model=model,
            tier=spec.tier,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cost_usd=pricing.cost(spec.tier, in_tokens, out_tokens),
            parsed=parsed,
        )
