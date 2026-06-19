"""The offline hunt — the whole engine runs end to end with no key and no infrastructure.

Drives the real Supervisor (real Emitter, real Boundary, real QwenClient in offline mode)
over an in-memory repo and asserts it reproduces flow_a: the same multiset of event types,
dense seq, every event valid against the FROZEN schema, the Boundary respected, no overspend.
This is the proof that the pipeline is correct before the model key ever arrives.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from app.engine.core import Emitter
from app.engine.supervisor import Supervisor
from app.events.models import load_event_schema
from app.qwen.client import QwenClient

from ._fakes import FakeRepo

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "flow_a_researcher.jsonl"


def _flow_a_type_counts() -> Counter:
    lines = [ln for ln in FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return Counter(json.loads(ln)["type"] for ln in lines)


async def test_offline_hunt_reproduces_flow_a() -> None:
    repo = FakeRepo()
    hunt_id = "hunt_offline"
    emitter = Emitter(hunt_id, repo)
    client = QwenClient()
    assert client.offline, "test env has no key, so the brain must be FakeQwen"

    commands: asyncio.Queue = asyncio.Queue()
    # The two human gates, pre-queued so the supervisor runs straight through.
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    commands.put_nowait(
        {"type": "resolve_hold", "hold_id": "x", "resolution": "Use the regulator figure (2M)"}
    )

    sup = Supervisor(
        hunt_id, emitter, repo, client, commands, source="typed", raw_input="BNPL Nigeria"
    )
    await asyncio.wait_for(sup.run(), timeout=10)

    events = repo.all_events(hunt_id)

    # seq is dense, 0-based, gap-free.
    assert [e.seq for e in events] == list(range(len(events)))

    # every emitted event validates against the frozen schema.
    validator = Draft202012Validator(load_event_schema())
    for e in events:
        errors = list(validator.iter_errors(e.model_dump()))
        assert not errors, f"seq {e.seq} ({e.type}) invalid: {[x.message for x in errors]}"

    # same event-type multiset as the canonical fixture.
    assert Counter(e.type for e in events) == _flow_a_type_counts()

    # it starts created and ends completed.
    assert events[0].type == "hunt_created"
    assert events[-1].type == "hunt_completed"

    # the Boundary was respected: no spend event ever exceeds the (first-hunt-capped) budget.
    boundary = next(e for e in events if e.type == "plan_approved").payload["boundary_usd"]
    for e in events:
        if e.type == "tokens_spent":
            assert e.payload["cumulative_usd"] <= boundary + 1e-9

    # the happy path stays well under budget — no boundary events at all.
    assert not any(e.type.startswith("boundary_") for e in events)
