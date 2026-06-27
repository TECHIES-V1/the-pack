"""Shadow Hunt (v2 safety rail) — rehearse a team's cost/time BEFORE spending, and sanity-check it.

Pure + deterministic: no model calls, no spend. Sums pricing.estimate() over a per-strategy call
list derived from the team, so the Plan can show "this team would cost ~$X, ~Y min" and flag a team
that won't run well — before the Packmaster sends the pack.
"""

from __future__ import annotations

from app.qwen import pricing

_DEFAULT_SCOUTS = 3
_KNOWN_ROLES = {"alpha", "beta", "scout", "tracker", "sentinel", "howler", "elder", "doctor"}


def _scout_count(team: list[dict]) -> int:
    n = sum(int(e.get("count") or 0) for e in team if e.get("role") == "scout")
    return n or _DEFAULT_SCOUTS


def validate_team(team: list[dict]) -> list[str]:
    """Human-readable warnings about a team. Empty = good to go (the engine clamps anyway)."""
    warnings: list[str] = []
    scouts = _scout_count(team)
    if scouts > 5:
        warnings.append(f"{scouts} scouts is a lot — the engine will cap it at 5.")
    unknown = sorted({str(e.get("role")) for e in team if str(e.get("role")) not in _KNOWN_ROLES})
    if unknown:
        warnings.append(f"Unknown role(s) will be dropped: {', '.join(unknown)}.")
    return warnings


def rehearse(team: list[dict], strategy: str) -> dict:
    """Estimate a hunt's cost (USD) and time (s) for this team + strategy, without running it."""
    scouts = max(1, min(5, _scout_count(team)))
    rounds = 2 if strategy == "deep_dive" else 1
    calls: list[str] = []
    calls += ["flash"] * (scouts * rounds)  # each scout summarizes its angle, per round
    calls += ["plus"] * rounds  # tracker merges, per round
    if strategy == "deep_dive":
        calls.append("plus")  # tracker names the gaps
    calls.append("max")  # sentinel critique (every strategy now)
    if strategy == "critique":
        calls += ["plus", "plus", "max"]  # a standoff: challenge, defend, judge
    calls.append("plus")  # howler drafts the brief
    est_cost = round(sum(pricing.estimate(t) for t in calls), 4)
    # Scouts run in parallel, so wall-clock ≈ rounds*(search+read) + merge + critique + draft.
    est_time = int(rounds * 30 + 20 + 15 + 20)
    return {
        "est_cost_usd": est_cost,
        "est_time_s": est_time,
        "calls": len(calls),
        "scouts": scouts,
        "warnings": validate_team(team),
    }
