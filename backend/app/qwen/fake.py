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

# Synthetic token usage per tier (input, output) — sized so cost is visible on the Boundary
# meter but a full multi-step hunt (scouts + merge + critique + a real Standoff + draft) stays
# comfortably inside the $0.50 first-hunt cap. Real Qwen calls are cheaper still.
_USAGE_BY_TIER: dict[str, tuple[int, int]] = {
    "flash": (20_000, 5_000),
    "plus": (28_000, 7_000),
    "max": (16_000, 4_000),
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
            "team": [{"role": "scout", "count": 3}],
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
    if intent == "standoff_challenge":
        return f"That claim on {task} leans on a single source — it needs a second to stand.", None
    if intent == "standoff_defend":
        return "Fair point — I'll pull a corroborating source before it goes in the brief.", None
    if intent == "standoff_judge":
        return "Alpha's call: keep the claim, but only once a second source backs it.", None
    if intent == "lone":
        text = (
            f"# {task}\n\nA single-pass briefing on {task}. One researcher, one read: the broad "
            "strokes are here, but with less cross-checking and fewer sources than a full pack hunt."
        )
        return text, None
    if intent == "judge":
        # The pack should win on depth + citations — that's the whole point of the Scorecard.
        return "Scored both briefings.", {"pack": 0.88, "lone": 0.62}
    if intent == "draft":
        # v3: Howler writes TAGGED blocks so each line carries its sources (trace).
        parsed = {
            "title": f"Briefing: {task}",
            "blocks": [
                {"text": f"What the pack found on {task}, from cited sources.", "source_ids": [1]},
                {"text": f"The leading players in {task} are taking shape.", "source_ids": [1, 2]},
                {"text": f"The key risk in {task}, and what changes next.", "source_ids": [2]},
            ],
        }
        text = "\n\n".join(b["text"] for b in parsed["blocks"])
        return text, parsed
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
