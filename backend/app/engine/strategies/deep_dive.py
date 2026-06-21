"""Iterative deep-research — search, read, find the gaps, search again.

Scouts range on the first angles, Tracker merges, then Tracker names what's still missing and
the pack ranges a second time on those gaps before the final synthesis. Best when the topic
rewards depth over breadth.
"""

from __future__ import annotations

import asyncio

from app.engine.strategies.base import Engine, Strategy


class DeepDiveStrategy(Strategy):
    name = "deep_dive"
    pattern = "parallel_then_merge"
    label = "Iterative deep-research"

    async def execute(self, engine: Engine) -> None:
        ids = engine.scout_ids()
        queries = engine.queries()

        # First round: the scouts range in parallel.
        results = await asyncio.gather(*(engine.scout(w, q) for w, q in zip(ids, queries)))
        findings = [f for f in results if f]

        merged = await engine.merge(findings)

        # The iterative core: name the gaps, then range again (in parallel) to close them.
        gaps = await engine.find_gaps(merged)
        if gaps and ids:
            await engine.progress("alpha", "thinking", f"Found {len(gaps)} gaps — sending the pack back in.")
            extra = await asyncio.gather(
                *(engine.scout(ids[i % len(ids)], gap, step_id="s1b") for i, gap in enumerate(gaps[:2]))
            )
            findings.extend(f for f in extra if f)
            merged = await engine.merge(findings, step_id="s2b")

        decision = None
        if merged.conflict:
            decision = await engine.resolve_conflict(merged.conflict)

        draft = await engine.draft(merged, decision)
        await engine.finish(draft, merged)
