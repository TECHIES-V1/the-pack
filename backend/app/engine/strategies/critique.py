"""Plan-execute-critique — Sentinel keeps the pack honest.

Scouts range, Tracker merges, then Sentinel challenges the weakest claim in a Standoff. The
pack takes one corrective pass before drafting. Best when the answer must be defensible.
"""

from __future__ import annotations

import asyncio

from app.engine.strategies.base import Engine, Strategy


class CritiqueStrategy(Strategy):
    name = "critique"
    pattern = "standoff"
    label = "Plan-execute-critique"

    async def execute(self, engine: Engine) -> None:
        ids = engine.scout_ids()
        queries = engine.queries()

        # The scouts range in parallel before Sentinel scrutinizes the merge.
        results = await asyncio.gather(*(engine.scout(w, q) for w, q in zip(ids, queries)))
        findings = [f for f in results if f]

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
