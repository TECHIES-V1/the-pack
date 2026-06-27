"""Strategy contract — the shape every research strategy plugs into (Doc 04 §04).

A strategy owns the EXECUTION phase of a hunt: after the user approves Beta's plan and the
pack is spawned, the Supervisor hands control to the chosen strategy's `execute(engine)`. The
strategy orchestrates a sequence of real research primitives — scout, merge, hold, critique,
standoff, draft — exposed by the `Engine` it's handed. The Supervisor IS the engine; this
Protocol keeps the strategies import-clean (no dependency back on the Supervisor module).

The differences between strategies live ONLY in how they sequence those primitives:
  * orchestrate — dynamic: scout → merge → (hold on conflict) → draft, rerouting on a Stray.
  * deep_dive   — iterative: scout → merge → find gaps → scout again → merge → draft.
  * critique    — rigorous: scout → merge → Sentinel critique → (standoff) → draft.

Each primitive is REAL (a live Qwen call + real web search) or its deterministic offline
twin (FakeQwen + the canned search provider) — the strategy can't tell and doesn't care.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# --- data passed between primitives -------------------------------------------------------


@dataclass
class Finding:
    """One scout's contribution: a summary plus the REAL sources it rests on (never invented —
    sources come from the web_search tool result, not the model)."""

    wolf_id: str
    summary: str
    sources: list[dict] = field(default_factory=list)
    confidence: float = 0.75
    output_ref: str | None = None


@dataclass
class Conflict:
    """A genuine disagreement Tracker surfaced in the findings — becomes a Hold for the human."""

    question: str
    options: list[str]
    recommended: str
    context_ref: str | None = None


@dataclass
class Merged:
    """Tracker's synthesis: a cross-referenced summary, the extracted claims, and any conflict."""

    summary: str
    claims: list[str] = field(default_factory=list)
    conflict: Conflict | None = None
    output_ref: str | None = None
    sources: list[dict] = field(default_factory=list)


@dataclass
class CritiqueResult:
    """Sentinel's verdict on the merged claims."""

    ok: bool
    issues: list[dict] = field(default_factory=list)  # [{claim, problem}]


# --- structured-output schemas the wolves are asked to fill (json_schema response format) ---

PLAN_SCHEMA: dict = {
    "type": "object",
    "required": ["summary", "queries", "assumptions", "est_cost", "est_time"],
    "properties": {
        "summary": {"type": "string"},
        # one search angle per scout — this is what makes the hunt topic-aware.
        "queries": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "est_cost": {"type": "number"},
        "est_time": {"type": "number"},
        # v2: the team Alpha should build — Beta sizes the pack to the task (mainly the scout count).
        "team": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"role": {"type": "string"}, "count": {"type": "integer"}},
            },
        },
    },
}

FINDINGS_SCHEMA: dict = {
    "type": "object",
    "required": ["summary", "confidence"],
    "properties": {
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
    },
}

MERGE_SCHEMA: dict = {
    "type": "object",
    "required": ["summary", "claims"],
    "properties": {
        "summary": {"type": "string"},
        "claims": {"type": "array", "items": {"type": "string"}},
        "conflict": {
            "type": ["object", "null"],
            "properties": {
                "question": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
                "recommended": {"type": "string"},
            },
        },
    },
}

CRITIQUE_SCHEMA: dict = {
    "type": "object",
    "required": ["ok", "issues"],
    "properties": {
        "ok": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"claim": {"type": "string"}, "problem": {"type": "string"}},
            },
        },
    },
}

GAPS_SCHEMA: dict = {
    "type": "object",
    "required": ["gaps"],
    "properties": {"gaps": {"type": "array", "items": {"type": "string"}}},
}


# --- the engine surface a strategy drives -------------------------------------------------


@runtime_checkable
class Engine(Protocol):
    """The research primitives a strategy orchestrates. Implemented by the Supervisor."""

    @property
    def task(self) -> str: ...

    @property
    def plan(self) -> dict: ...

    def scout_ids(self) -> list[str]: ...

    def queries(self) -> list[str]: ...

    async def scout(self, wolf_id: str, query: str, step_id: str = "s1") -> Finding: ...

    async def merge(self, findings: list[Finding], step_id: str = "s2") -> Merged: ...

    async def resolve_conflict(self, conflict: Conflict) -> str: ...

    async def find_gaps(self, merged: Merged) -> list[str]: ...

    async def critique(self, merged: Merged) -> CritiqueResult: ...

    async def standoff(
        self, challenger: str, defendant: str, claim_ref: str, rationale: str
    ) -> None: ...

    async def draft(self, merged: Merged, decision: str | None = None, step_id: str = "s3") -> str: ...

    async def finish(self, draft_text: str, merged: Merged) -> None: ...

    async def progress(self, wolf_id: str, phase: str, text: str) -> None: ...


# --- the strategy base --------------------------------------------------------------------


class Strategy:
    """Base class. `name` keys the registry; `pattern` is the plan_proposed coordination shape."""

    name: str = "base"
    pattern: str = "parallel_then_merge"
    label: str = "Base"

    async def execute(self, engine: Engine) -> None:  # pragma: no cover - overridden
        raise NotImplementedError
