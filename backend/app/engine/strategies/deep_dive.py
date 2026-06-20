"""Iterative deep-research — search, read, find the gaps, search again.

Scouts range on the first angles, Tracker merges, then Tracker names what's still missing and
the pack ranges a second time on those gaps before the final synthesis. Best when the topic
rewards depth over breadth.
"""

from __future__ import annotations

from app.engine.strategies.base import Engine, Strategy


class DeepDiveStrategy(Strategy):
    name = "deep_dive"
    pattern = "parallel_then_merge"
    label = "Iterative deep-research"

    async def execute(self, engine: Engine) -> None:
        ids = engine.scout_ids()
        queries = engine.queries()

        findings = []
        for wolf_id, query in zip(ids, queries):
            finding = await engine.scout(wolf_id, query)
            if finding:
                findings.append(finding)

        merged = await engine.merge(findings)

        # The iterative core: name the gaps, then range again to close them.
        gaps = await engine.find_gaps(merged)
        if gaps and ids:
            await engine.progress("alpha", "thinking", f"Found {len(gaps)} gaps — sending the pack back in.")
            for i, gap in enumerate(gaps[:2]):
                extra = await engine.scout(ids[i % len(ids)], gap, step_id="s1b")
                if extra:
                    findings.append(extra)
            merged = await engine.merge(findings, step_id="s2b")

        decision = None
        if merged.conflict:
            decision = await engine.resolve_conflict(merged.conflict)

        draft = await engine.draft(merged, decision)
        await engine.finish(draft, merged)
