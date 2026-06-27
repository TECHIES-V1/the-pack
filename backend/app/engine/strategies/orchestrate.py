"""Dynamic orchestrator — Alpha leads, the pack adapts (Magentic-One's spirit).

Scouts range on the plan's angles, Tracker merges, and a Hold surfaces ONLY when a real
conflict appears in the findings. The default strategy: the broadest, most adaptive shape.
"""

from __future__ import annotations

import asyncio

from app.engine.strategies.base import Engine, Strategy


class OrchestrateStrategy(Strategy):
    name = "orchestrate"
    pattern = "hierarchical"
    label = "Dynamic orchestrator"

    async def execute(self, engine: Engine) -> None:
        ids = engine.scout_ids()
        queries = engine.queries()

        # The scouts range in PARALLEL — that's where the pack structurally wins on latency.
        results = await asyncio.gather(*(engine.scout(w, q) for w, q in zip(ids, queries)))
        findings = [f for f in results if f]

        # Adaptive touch: if the pack came back thin (a scout failed), broaden and range again.
        if len([f for f in findings if f.confidence >= 0.4]) < 2 and ids:
            await engine.progress("alpha", "thinking", "Findings look thin — sending a scout back out.")
            retry = await engine.scout(ids[0], f"{engine.task} overview and key facts", step_id="s1b")
            if retry:
                findings.append(retry)

        merged = await engine.merge(findings)

        # Sentinel verifies every claim carries a real source before we draft — a real check that
        # also wakes the Sentinel node on the canvas (the default strategy used to skip it).
        await engine.critique(merged)

        decision = None
        if merged.conflict:
            decision = await engine.resolve_conflict(merged.conflict)

        draft = await engine.draft(merged, decision)
        await engine.finish(draft, merged)
