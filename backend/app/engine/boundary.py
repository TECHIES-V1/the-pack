"""The Boundary — a gate BEFORE the call, not a graph after it (Doc 04 §04, F7).

Every LLM and tool call passes a gate that checks PROJECTED spend before dispatch:
  * 70%  -> emit boundary_warning
  * 85%  -> apply the downgrade policy (flash-tier non-critical wolves, thinking off where
            safe) and emit boundary_downgrade
  * 100% -> BLOCK the call, checkpoint, and emit boundary_halt

This must INTERCEPT, never merely observe. It is the market gap we demonstrate. First
hunts carry a silent $0.50 cap regardless of settings. Per-wolf sub-budgets enforced the
same way.

Scaffold: the thresholds and the gate signature are fixed here; the engine wires dispatch
through `check()` so no call can escape it. See fixtures/boundary_halt.jsonl for the
expected event sequence and backend/tests for the assertion that nothing dispatches >100%.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Verdict(StrEnum):
    OK = "ok"
    WARN = "warn"  # >=70%
    DOWNGRADE = "downgrade"  # >=85%
    HALT = "halt"  # >=100%, block the call


WARN_PCT = 70.0
DOWNGRADE_PCT = 85.0
HALT_PCT = 100.0


@dataclass
class Boundary:
    boundary_usd: float
    cumulative_usd: float = 0.0

    def projected_pct(self, next_call_usd: float) -> float:
        if self.boundary_usd <= 0:
            return 100.0
        return (self.cumulative_usd + next_call_usd) / self.boundary_usd * 100.0

    def check(self, next_call_usd: float) -> Verdict:
        """Decide BEFORE dispatch. The engine must not dispatch on HALT."""
        pct = self.projected_pct(next_call_usd)
        if pct >= HALT_PCT:
            return Verdict.HALT
        if pct >= DOWNGRADE_PCT:
            return Verdict.DOWNGRADE
        if pct >= WARN_PCT:
            return Verdict.WARN
        return Verdict.OK
