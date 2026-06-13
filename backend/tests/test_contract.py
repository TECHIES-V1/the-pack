"""Contract tests (Doc 04 §8): every event validates against the schema; the fixtures stay green.

These run with no network and no Redis — pure schema + invariant checks over the committed
fixture pack. CI gates on them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.events.models import EVENT_TYPES, load_event_schema

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES_DIR = BACKEND / "fixtures"
FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.jsonl"))


def _load(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_fixtures_exist() -> None:
    names = {p.name for p in FIXTURE_FILES}
    assert names == {
        "flow_a_researcher.jsonl",
        "flow_b_meeting.jsonl",
        "boundary_halt.jsonl",
        "standoff_stray.jsonl",
    }, f"unexpected fixture set: {names}"


def test_schema_itself_is_valid() -> None:
    Draft202012Validator.check_schema(load_event_schema())


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.name)
def test_every_event_validates(path: Path) -> None:
    validator = Draft202012Validator(load_event_schema())
    for i, event in enumerate(_load(path)):
        errors = sorted(validator.iter_errors(event), key=str)
        assert not errors, f"{path.name} line {i}: {[e.message for e in errors]}"


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.name)
def test_seq_strictly_increasing_per_hunt(path: Path) -> None:
    events = _load(path)
    by_hunt: dict[str, list[int]] = {}
    for ev in events:
        by_hunt.setdefault(ev["hunt_id"], []).append(ev["seq"])
    for hunt_id, seqs in by_hunt.items():
        assert seqs[0] == 0, f"{path.name}: {hunt_id} must start at seq 0"
        assert seqs == list(range(len(seqs))), (
            f"{path.name}: {hunt_id} seq not contiguous-increasing"
        )


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.name)
def test_event_types_known(path: Path) -> None:
    for ev in _load(path):
        assert ev["type"] in EVENT_TYPES, f"{path.name}: unknown type {ev['type']!r}"


def test_boundary_halts_before_overspend() -> None:
    """The Boundary test: nothing dispatches past 100%; halt is terminal."""
    events = _load(FIXTURES_DIR / "boundary_halt.jsonl")
    types = [e["type"] for e in events]
    assert types[-1] == "boundary_halt", "boundary_halt must be the terminal event"
    assert "boundary_warning" in types and "boundary_downgrade" in types

    boundary = next(e for e in events if e["type"] == "plan_approved")["payload"]["boundary_usd"]
    halt_index = types.index("boundary_halt")
    # No spend event AFTER the halt (no call dispatched past 100%).
    assert "tokens_spent" not in types[halt_index + 1 :]
    # Cumulative never exceeds the boundary at the moment of any recorded spend.
    for e in events:
        if e["type"] == "tokens_spent":
            assert e["payload"]["cumulative_usd"] <= boundary + 1e-9
