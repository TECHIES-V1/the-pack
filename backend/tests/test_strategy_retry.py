"""Part 2: the orchestrate strategy re-ranges EVERY thin scout — not just scout-1.

This is the regression guard for the 'only one scout works' bug: the old code re-ran a hardcoded
`ids[0]`, so when the whole pack came back thin only the first scout ever recovered.
"""

from __future__ import annotations

from app.engine.strategies.base import CritiqueResult, Finding, Merged
from app.engine.strategies.orchestrate import OrchestrateStrategy


class _RecordingEngine:
    """A minimal Engine the orchestrate strategy can drive. Scouts come back THIN on their first
    angle (s1) and find ground on the broad retry (s1b) — so we can assert which scouts re-ran."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self.scout_calls: list[tuple[str, str, str]] = []
        self.merged: list[Finding] = []

    @property
    def task(self) -> str:
        return "the topic"

    def scout_ids(self) -> list[str]:
        return self._ids

    def queries(self) -> list[str]:
        return [f"angle for {w}" for w in self._ids]

    async def scout(self, wolf_id: str, query: str, step_id: str = "s1") -> Finding:
        self.scout_calls.append((wolf_id, query, step_id))
        recovered = step_id == "s1b"  # the broad retry finds ground; the first angle was dry
        return Finding(
            wolf_id=wolf_id,
            summary="found" if recovered else "",
            sources=[{"url": f"https://e.com/{wolf_id}"}] if recovered else [],
            confidence=0.8 if recovered else 0.0,
        )

    async def merge(self, findings: list[Finding], step_id: str = "s2") -> Merged:
        self.merged = findings
        return Merged(summary="m", claims=["c"], sources=[s for f in findings for s in f.sources])

    async def critique(self, merged: Merged) -> CritiqueResult:
        return CritiqueResult(ok=True, issues=[])

    async def resolve_conflict(self, conflict: object) -> str:
        return "decided"

    async def draft(self, merged: Merged, decision: str | None = None, step_id: str = "s3") -> str:
        return "draft"

    async def finish(self, draft_text: str, merged: Merged) -> None:
        self.finished = True

    async def progress(self, wolf_id: str, phase: str, text: str) -> None:
        return None


async def test_orchestrate_reruns_every_thin_scout_not_just_the_first() -> None:
    eng = _RecordingEngine(["scout-1", "scout-2", "scout-3"])
    await OrchestrateStrategy().execute(eng)

    # All three scouts ranged first (s1); since all came back thin, ALL THREE re-ran (s1b).
    first_pass = sorted(w for (w, _q, step) in eng.scout_calls if step == "s1")
    retried = sorted(w for (w, _q, step) in eng.scout_calls if step == "s1b")
    assert first_pass == ["scout-1", "scout-2", "scout-3"]
    assert retried == ["scout-1", "scout-2", "scout-3"], "every thin scout re-runs, not just one"

    # The merge sees one good finding per scout — the pack, not a lone wolf.
    assert len([f for f in eng.merged if f.confidence >= 0.4]) == 3
