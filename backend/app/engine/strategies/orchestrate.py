"""Dynamic orchestrator — Alpha leads, the pack adapts (Magentic-One's spirit).

Scouts range on the plan's angles, Tracker merges, and a Hold surfaces ONLY when a real
conflict appears in the findings. The default strategy: the broadest, most adaptive shape.
"""

from __future__ import annotations

import asyncio

from app.engine.strategies.base import Engine, Strategy

# When the pack still comes back thin, re-range EVERY thin scout (not just the first), each on a
# different broad facet so their retries don't all collapse onto the same source — the pack's whole
# value is diverse ground.
_RETRY_FACETS = ["overview and key facts", "latest developments", "analysis and context"]
_OK = 0.4  # a finding clears this confidence ⇒ it stands; below ⇒ the scout came back thin


class OrchestrateStrategy(Strategy):
    name = "orchestrate"
    pattern = "hierarchical"
    label = "Dynamic orchestrator"

    async def execute(self, engine: Engine) -> None:
        ids = engine.scout_ids()
        queries = engine.queries()

        # The scouts range in PARALLEL — that's where the pack structurally wins on latency.
        pairs = list(zip(ids, queries, strict=False))
        results = await asyncio.gather(*(engine.scout(w, q) for w, q in pairs))
        findings = [f for f in results if f]

        # Adaptive: if the pack still came back thin, send EVERY thin scout back out (not just one),
        # each on a different broad facet, and fold the recoveries back in by scout.
        if len([f for f in findings if f.confidence >= _OK]) < 2 and ids:
            thin = [f.wolf_id for f in findings if f.confidence < _OK] or ids
            await engine.progress("alpha", "thinking", "Findings look thin — ranging again.")
            jobs = [
                (wid, f"{engine.task} {_RETRY_FACETS[i % len(_RETRY_FACETS)]}")
                for i, wid in enumerate(thin)
            ]
            retries = await asyncio.gather(
                *(engine.scout(wid, q, step_id="s1b") for wid, q in jobs)
            )
            by_id = {f.wolf_id: f for f in findings}
            for r in retries:
                if r and r.confidence >= _OK:  # keep the recovery only if it actually found ground
                    by_id[r.wolf_id] = r
            findings = list(by_id.values())

        merged = await engine.merge(findings)

        # Sentinel verifies every claim carries a real source before we draft — a real check that
        # also wakes the Sentinel node on the canvas (the default strategy used to skip it).
        await engine.critique(merged)

        decision = None
        if merged.conflict:
            decision = await engine.resolve_conflict(merged.conflict)

        draft = await engine.draft(merged, decision)
        await engine.finish(draft, merged)
