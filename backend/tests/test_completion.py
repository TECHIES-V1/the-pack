"""Engine completion tests — the features that were stubbed/dead now fire, all offline.

Covers: plan edits (A6), mid-hunt input (A7), and Stray timeout detection/recovery (A3).
Parallel scouts (A1), web_fetch (A4), and real Standoffs (A2) are exercised by the existing
offline-hunt tests; here we add the paths those don't reach.
"""

from __future__ import annotations

import asyncio

from jsonschema import Draft202012Validator

from app.engine.benchmark import run_benchmark
from app.engine.core import Emitter
from app.engine.supervisor import Supervisor
from app.events.models import load_event_schema
from app.qwen.client import QwenClient
from app.qwen.fake import FakeQwen
from app.qwen.types import CallSpec, CompletionResult

from ._fakes import FakeRepo


async def _drive(commands: asyncio.Queue, *, strategy: str = "orchestrate", client=None, timeout=15):
    repo = FakeRepo()
    hunt_id = f"hunt_{strategy}"
    emitter = Emitter(hunt_id, repo)
    sup = Supervisor(
        hunt_id,
        emitter,
        repo,
        client or QwenClient(),
        commands,
        source="typed",
        raw_input="the BNPL market in Nigeria",
        strategy=strategy,
    )
    await asyncio.wait_for(sup.run(), timeout=timeout)
    return sup, repo.all_events(hunt_id)


async def test_plan_edits_apply_and_emit() -> None:
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait(
        {
            "type": "approve_plan",
            "mode": "on_signal",
            "boundary_usd": 1.0,
            "edits": {"queries": ["custom alpha query", "custom beta query", "custom gamma query"]},
        }
    )
    _, events = await _drive(commands)

    assert any(e.type == "plan_edited" for e in events), "an edit must emit plan_edited"
    searches = [
        e.payload["args_summary"]
        for e in events
        if e.type == "tool_called" and e.payload.get("tool") == "web_search"
    ]
    assert "custom alpha query" in searches, "scouts must search the EDITED queries"


async def test_mid_hunt_input_is_absorbed() -> None:
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    commands.put_nowait({"type": "add_input", "text": "Focus on the under-25 segment.", "kind": "text"})
    sup, events = await _drive(commands)

    assert any(e.type == "input_added" and e.payload.get("mid_hunt") for e in events)
    assert any("under-25" in t for t in sup._extra_inputs)


class _SlowClient:
    """Offline brain that stalls before answering — used to trip the step timeout (Stray)."""

    def __init__(self, delay: float) -> None:
        self.offline = True
        self._fake = FakeQwen()
        self._delay = delay

    async def complete(self, spec: CallSpec, on_delta=None) -> CompletionResult:
        await asyncio.sleep(self._delay)
        return await self._fake.complete(spec, on_delta)


async def test_stray_timeout_detects_and_recovers() -> None:
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})

    repo = FakeRepo()
    emitter = Emitter("hunt_slow", repo)
    sup = Supervisor(
        "hunt_slow", emitter, repo, _SlowClient(0.2), commands, raw_input="a topic", strategy="orchestrate"
    )
    sup._step_timeout = 0.05  # a scout that takes 0.2s now overruns and is ruled a Stray
    await asyncio.wait_for(sup.run(), timeout=20)
    events = repo.all_events("hunt_slow")

    assert any(e.type == "stray_detected" and e.payload["pattern"] == "timeout" for e in events)
    assert any(e.type == "stray_recovered" for e in events)
    # the hunt still finishes — a Stray reroutes, it doesn't kill the hunt.
    assert events[-1].type == "hunt_completed"


async def test_benchmark_scores_pack_above_lone() -> None:
    # First run a real (offline) pack hunt to completion.
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    repo = FakeRepo()
    emitter = Emitter("hb", repo)
    sup = Supervisor("hb", emitter, repo, QwenClient(), commands, raw_input="the topic", strategy="orchestrate")
    await asyncio.wait_for(sup.run(), timeout=15)

    # Then benchmark it against a fresh lone wolf (continues the same event stream).
    scorecard = await run_benchmark("hb", emitter, repo, QwenClient(), "the topic")
    events = repo.all_events("hb")

    assert any(e.type == "benchmark_started" for e in events)
    completed = [e for e in events if e.type == "benchmark_completed"]
    assert completed, "benchmark must emit benchmark_completed"

    validator = Draft202012Validator(load_event_schema())
    assert not list(validator.iter_errors(completed[0].model_dump())), "scorecard must be schema-valid"
    assert scorecard["pack"]["quality"] >= scorecard["lone_wolf"]["quality"]
    assert [e.seq for e in events] == list(range(len(events))), "seq stays dense through the benchmark"


async def test_resume_after_boundary_halt() -> None:
    commands: asyncio.Queue = asyncio.Queue()
    # A tiny Boundary halts at the first expensive (merge) call...
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 0.02})
    # ...and a queued resume raises it so the hunt continues from exactly where it paused.
    commands.put_nowait({"type": "resume", "boundary_usd": 1.0})
    _, events = await _drive(commands)

    assert any(e.type == "boundary_halt" for e in events), "the tiny Boundary must halt the hunt"
    assert events[-1].type == "hunt_completed", "resume must let the hunt finish"
    # nothing was dispatched past 100% before the resume.
    boundary = next(e for e in events if e.type == "plan_approved").payload["boundary_usd"]
    halt_idx = next(i for i, e in enumerate(events) if e.type == "boundary_halt")
    pre_halt_spend = [
        e.payload["cumulative_usd"] for e in events[:halt_idx] if e.type == "tokens_spent"
    ]
    assert all(s <= boundary + 1e-9 for s in pre_halt_spend)
