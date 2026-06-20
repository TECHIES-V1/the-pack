"""Dynamic orchestrator — Alpha leads, the pack adapts (Magentic-One's spirit).

Scouts range on the plan's angles, Tracker merges, and a Hold surfaces ONLY when a real
conflict appears in the findings. The default strategy: the broadest, most adaptive shape.
"""

from __future__ import annotations

from app.engine.strategies.base import Engine, Strategy


class OrchestrateStrategy(Strategy):
    name = "orchestrate"
    pattern = "hierarchical"
    label = "Dynamic orchestrator"

    async def execute(self, engine: Engine) -> None:
        ids = engine.scout_ids()
        queries = engine.queries()

        findings = []
        for wolf_id, query in zip(ids, queries):
            finding = await engine.scout(wolf_id, query)
            if finding:
                findings.append(finding)

        # Adaptive touch: if the pack came back thin (a scout failed), broaden and range again.
        if len([f for f in findings if f.confidence >= 0.4]) < 2 and ids:
            await engine.progress("alpha", "thinking", "Findings look thin — sending a scout back out.")
            retry = await engine.scout(ids[0], f"{engine.task} overview and key facts", step_id="s1b")
            if retry:
                findings.append(retry)

        merged = await engine.merge(findings)

        decision = None
        if merged.conflict:
            decision = await engine.resolve_conflict(merged.conflict)

        draft = await engine.draft(merged, decision)
        await engine.finish(draft, merged)
