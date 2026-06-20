"""Plan-execute-critique — Sentinel keeps the pack honest.

Scouts range, Tracker merges, then Sentinel challenges the weakest claim in a Standoff. The
pack takes one corrective pass before drafting. Best when the answer must be defensible.
"""

from __future__ import annotations

from app.engine.strategies.base import Engine, Strategy


class CritiqueStrategy(Strategy):
    name = "critique"
    pattern = "standoff"
    label = "Plan-execute-critique"

    async def execute(self, engine: Engine) -> None:
        ids = engine.scout_ids()
        queries = engine.queries()

        findings = []
        for wolf_id, query in zip(ids, queries):
            finding = await engine.scout(wolf_id, query)
            if finding:
                findings.append(finding)

        merged = await engine.merge(findings)

        # The critique core: Sentinel challenges the weakest claim, then the pack corrects.
        verdict = await engine.critique(merged)
        if not verdict.ok and verdict.issues:
            issue = verdict.issues[0]
            await engine.standoff(
                challenger="sentinel",
                defendant="tracker",
                claim_ref=merged.output_ref or f"art_{engine.task[:8]}_merge",
                rationale=issue.get("problem", "A claim needs a stronger source."),
            )
            merged = await engine.merge(findings, step_id="s2b")

        decision = None
        if merged.conflict:
            decision = await engine.resolve_conflict(merged.conflict)

        draft = await engine.draft(merged, decision)
        await engine.finish(draft, merged)
