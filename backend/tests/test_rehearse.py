"""Shadow Hunt rehearsal (v2) — a pure, deterministic cost/time estimate + team validation."""

from __future__ import annotations

from app.engine.rehearse import rehearse, validate_team


def test_rehearse_scales_with_scouts() -> None:
    one = rehearse([{"role": "scout", "count": 1}], "orchestrate")
    five = rehearse([{"role": "scout", "count": 5}], "orchestrate")
    assert one["scouts"] == 1 and five["scouts"] == 5
    assert five["est_cost_usd"] > one["est_cost_usd"] > 0
    assert five["est_time_s"] > 0


def test_rehearse_deep_dive_costs_more() -> None:
    team = [{"role": "scout", "count": 3}]
    deep = rehearse(team, "deep_dive")["est_cost_usd"]
    shallow = rehearse(team, "orchestrate")["est_cost_usd"]
    assert deep > shallow


def test_validate_team_flags_issues() -> None:
    assert any("cap" in w for w in validate_team([{"role": "scout", "count": 9}]))
    assert validate_team([{"role": "scout", "count": 3}]) == []
    assert any("dropped" in w for w in validate_team([{"role": "wizard", "count": 1}]))
