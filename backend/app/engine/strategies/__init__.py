"""Research strategies — the selectable engine modes (Doc 04 §04).

`strategy` (orchestrate | deep_dive | critique) is chosen by the user at the Door and shapes
how the pack works. It is ORTHOGONAL to the autonomy `mode` (wild | on_signal | on_command),
which shapes how much it pauses for the human. The Supervisor resolves the name through
`get_strategy` and hands it the engine to drive.
"""

from __future__ import annotations

from app.engine.strategies.base import (
    Conflict,
    CritiqueResult,
    Engine,
    Finding,
    Merged,
    Strategy,
)
from app.engine.strategies.critique import CritiqueStrategy
from app.engine.strategies.deep_dive import DeepDiveStrategy
from app.engine.strategies.orchestrate import OrchestrateStrategy

_REGISTRY: dict[str, type[Strategy]] = {
    OrchestrateStrategy.name: OrchestrateStrategy,
    DeepDiveStrategy.name: DeepDiveStrategy,
    CritiqueStrategy.name: CritiqueStrategy,
}

DEFAULT_STRATEGY = OrchestrateStrategy.name


def get_strategy(name: str | None) -> Strategy:
    """Resolve a strategy name to an instance, falling back to the default on anything unknown."""
    cls = _REGISTRY.get((name or "").strip().lower(), OrchestrateStrategy)
    return cls()


def strategy_catalog() -> list[dict]:
    """The selectable modes, for the Door's picker (name, label, pattern)."""
    return [
        {"name": c.name, "label": c.label, "pattern": c.pattern}
        for c in (OrchestrateStrategy, DeepDiveStrategy, CritiqueStrategy)
    ]


__all__ = [
    "Conflict",
    "CritiqueResult",
    "Engine",
    "Finding",
    "Merged",
    "Strategy",
    "get_strategy",
    "strategy_catalog",
    "DEFAULT_STRATEGY",
]
